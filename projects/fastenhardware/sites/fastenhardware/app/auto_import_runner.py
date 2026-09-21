"""Local-first importer. `--dry-run` is offline and cannot write WooCommerce.

Known stages are reusable; unfamiliar semantics become a per-offer review item.
No Codex runtime, chat SDK, LLM or remote image-generation dependency is imported.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import time
from xml.etree import ElementTree as ET
import zipfile

from .google_keyword_planner import GoogleKeywordPlanner, score_keywords
from .seo_title_builder import build_researched_title
from .runner_content import canonical, prepare_content, validate_source, select_category, deterministic_pack
from .runner_state import ReviewQueue, ReviewRequired, StageStore, digest, file_hash, read, save, now
from .strict_cache import rules_version, specification_hash

ROOT = Path(__file__).resolve().parents[1]


def read_tasks(value, start=None, end=None):
    if str(value).startswith(("https://", "http://")):
        tasks = [{"source_url": str(value)}]
    else:
        path = Path(value)
        if path.suffix.lower() == ".json":
            tasks = read(path)
        elif path.suffix.lower() == ".xlsx":
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            with zipfile.ZipFile(path) as z:
                strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    strings = ["".join(t.text or "" for t in i.iterfind(".//x:t", ns))
                               for i in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("x:si", ns)]
                sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
                links = {}
                relpath = "xl/worksheets/_rels/sheet1.xml.rels"
                if relpath in z.namelist():
                    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read(relpath))}
                    for link in sheet.findall(".//x:hyperlink", ns):
                        links[link.get("ref")] = rels.get(link.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
                tasks = []
                for row in sheet.findall(".//x:sheetData/x:row", ns):
                    cells = {}
                    for c in row.findall("x:c", ns):
                        text = c.findtext("x:v", "", ns)
                        if c.get("t") == "s":
                            text = strings[int(text)] if text else ""
                        elif c.get("t") == "inlineStr":
                            text = "".join(t.text or "" for t in c.iterfind(".//x:t", ns))
                        cells[re.sub(r"\d+$", "", c.get("r", ""))] = links.get(c.get("r")) or text
                    try:
                        sequence = int(float(cells.get("A", "")))
                    except ValueError:
                        continue
                    if (start is not None and sequence < start) or (end is not None and sequence > end):
                        continue
                    urls = [v.strip() for v in cells.values() if re.search(r"https?://detail\.1688\.com/offer/\d+\.html", v)]
                    if len(set(urls)) != 1:
                        raise ValueError(f"Excel sequence {sequence}: expected one product URL")
                    tasks.append({"sequence": sequence, "source_url": urls[0]})
            if start is not None and end is not None and [t["sequence"] for t in tasks] != list(range(start, end + 1)):
                raise ValueError("Excel selected sequence range incomplete or duplicated")
        else:
            raise ValueError("Input must be a 1688 URL, XLSX or explicit JSON task manifest")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Empty or invalid task manifest")
    for task in tasks:
        offer = canonical(task["source_url"])
        if task.get("offer_id") and str(task["offer_id"]) != offer:
            raise ValueError("Task URL/Offer ID mismatch")
        task["offer_id"] = offer
    if len({t["offer_id"] for t in tasks}) != len(tasks):
        raise ValueError("Duplicate Offer IDs in input")
    return tasks


@contextmanager
def exclusive_lock(path):
    """OS lock is released after a crash; protects cache and store idempotency."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Runner:
    def __init__(self, root=ROOT, *, dry_run=False, process_images=False, run_dir=None,
                 keyword_api=False, draft=False, poll_seconds=30):
        from .site_guard import ROOT as FIXED_ROOT, SKILL_DIR, preflight, contained
        preflight()
        if Path(root).resolve() != FIXED_ROOT.resolve():
            raise ValueError("HARD STOP: ROOT_OVERRIDE_FORBIDDEN")
        self.root = FIXED_ROOT
        self.dry_run, self.process_images, self.draft = dry_run, process_images, draft
        self.run_dir = Path(run_dir).resolve() if run_dir else self.root / "output/auto-runner" / ("dry-run" if dry_run else "live")
        contained(self.run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.version = rules_version(SKILL_DIR) + ":" + digest(
            [(p.name, file_hash(p)) for p in sorted((self.root / "app").glob("runner_*.py"))] +
            [(name, file_hash(self.root / "app" / name)) for name in
             ("google_keyword_planner.py", "seo_title_builder.py", "auto_import_runner.py")])
        self.queue = ReviewQueue(self.run_dir / "ai-review-queue.json")
        if not dry_run:
            from .site_guard import load_credentials
            load_credentials()
        self.planner = GoogleKeywordPlanner(self.root / "data/keyword-cache.json", allow_api=not dry_run and
            bool(keyword_api or os.environ.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH")))
        self.mapping = read(self.root / "data/keyword-map.json", [])
        self.store = None
        self.images = None
        self.poll_seconds = max(30, poll_seconds)
        self.session = "auto_import_1688_" + digest(str(self.root))[:12]
        self.verifications = read(self.run_dir / "verification-events.json", [])

    def source_path(self, offer):
        return self.root / "output" / offer / "original-product.json"

    def acquire(self, task):
        source_file = self.source_path(task["offer_id"])
        if source_file.exists():
            source = read(source_file)
            validate_source(source, task["source_url"])
            return source  # Never reacquire an existing complete source.
        if self.dry_run:
            raise ReviewRequired("OFFLINE_SOURCE_MISSING")
        from .batch20_collect_conservative import cli, collect_one, VerificationRequired
        from . import batch50_collect_conservative as session
        adapter = cli()
        session.SESSION_NAME = self.session
        pending = next((e for e in reversed(self.verifications) if e["offer_id"] == task["offer_id"] and not e.get("resume_success")), None)
        while True:
            if pending and not pending.get("verification_passed_at"):
                # Existing browser/profile is retained; never destroy it on pause.
                if not pending.get("headed_opened"):
                    session.open_verification_window(adapter, task["source_url"])
                    pending["headed_opened"] = True
                    save(self.run_dir / "verification-events.json", self.verifications)
                session.wait_for_manual_verification(adapter, task["offer_id"], self.poll_seconds)
                pending["verification_passed_at"] = now()
                pending["verification_duration"] = round(time.time() - pending["started_epoch"], 3)
                pending["whoami_confirmed"] = True
                save(self.run_dir / "verification-events.json", self.verifications)
                time.sleep(8)
            try:
                collect_one(adapter, task["offer_id"], self.root / "output", browser_session=self.session,
                            keep_browser_session=True, browser_window="background", resume_partial=True)
                source = read(source_file)
                source["source_url"] = task["source_url"]
                save(source_file, source)
                validate_source(source, task["source_url"])
                if pending:
                    pending["resume_success"] = True
                    save(self.run_dir / "verification-events.json", self.verifications)
                return source
            except VerificationRequired as exc:
                if pending:
                    pending["resume_success"] = False
                pending = dict(offer_id=task["offer_id"], verification_triggered_at=now(),
                               started_epoch=time.time(), verification_count=len(self.verifications) + 1,
                               verification_duration=None, resume_success=None, kind=exc.kind)
                self.verifications.append(pending)
                save(self.run_dir / "verification-events.json", self.verifications)
                # No new offer request until human verification and whoami pass.

    def process(self, task):
        started = time.perf_counter()
        queries = self.planner.keyword_api_queries
        hits = self.planner.cache_hits
        writes_before = self.store.write_count if self.store else 0
        offer = task["offer_id"]
        folder = self.run_dir / offer
        stages = StageStore(folder)
        audit = dict(offer_id=offer, local_processing=True, llm_calls=0, vision_calls=0, stages={}, warnings=[],
                     dry_run=self.dry_run, woocommerce_writes=0, started_at=now())
        try:
            source = self.acquire(task)
            audit["stages"]["acquisition"] = "EXISTING_SOURCE" if self.dry_run else "SOURCE_READY"
            audit["source_validation"] = validate_source(source, task["source_url"])
            product_dir = self.source_path(offer).parent
            from .runner_images import inventory, replay_existing, LocalImages
            raw = inventory(source, product_dir)
            image_key = digest([(r["filename"], r["raw_sha256"]) for r in raw])
            # Full input content+rules identity, never semantic matching.
            pack_path = Path(task.get("evidence_file") or product_dir / "runner-evidence.json")
            if not pack_path.is_absolute():
                pack_path = self.root / pack_path
            from .site_guard import contained
            contained(pack_path)
            pack = read(pack_path, {})
            if not pack:
                pack = deterministic_pack(source)
                save(folder / "generated-evidence.json", pack)
            processed = read(product_dir / "processed-product.json", {})
            content, event = stages.run("content", [digest(source), image_key, self.version, digest(pack), digest(processed)],
                lambda: prepare_content(source, pack, processed))
            audit["stages"]["content"] = event
            # Prices and IDs are validated even on a content CACHE_HIT.
            from .runner_content import priced_skus
            content["skus"] = priced_skus(source, content)
            words = list(dict.fromkeys(pack.get("seed_keywords", []) + list(pack.get("keyword_relevance", {}))))
            metrics = self.planner.query(words)
            ranked = score_keywords(metrics, pack.get("keyword_relevance", {}), self.mapping, offer)
            recommendation = build_researched_title(content["title"], ranked, pack.get("title_options", {}), pack.get("current_primary"))
            save(folder / "keyword-research.json", dict(rows=ranked, decision=recommendation,
                                                       trends="Evidence-only; no index treated as volume"))
            for row in ranked[:5]:
                if row["reason"] and row["reason"].startswith("SERP_"):
                    self.queue.add(offer, "serp", row["reason"], {"keyword": row["keyword"]})
            content["title"] = recommendation["title"]
            content["seo"].update(meta_title=content["title"], focus_keyword=recommendation["primary_keyword"] or "")
            audit["keyword_decision"] = recommendation
            if not any(r["eligible"] for r in ranked):
                audit["warnings"].append("KEYWORD_EVIDENCE_INSUFFICIENT_KEEP_CURRENT_TITLE")
            if self.dry_run:
                tree = pack.get("category_snapshot", [])
                audit["stages"]["category_source"] = "OFFLINE_SNAPSHOT_NOT_LIVE_ACCEPTANCE"
            else:
                if self.store is None:
                    from .runner_woocommerce import Store
                    self.store = Store()
                tree = self.store.categories
                audit["stages"]["category_source"] = "LIVE_REST_BATCH_CACHE"
            if not self.dry_run and pack.get("category_path"):
                from .fastener_categories import ensure_path
                leaf = ensure_path(self.store, pack["category_path"])
                terms = [leaf]
            else:
                terms = pack.get("category_terms", [])
            content["category"] = select_category(tree, content["facts"], terms)
            def image_stage():
                if self.dry_run and not self.process_images:
                    return replay_existing(source, processed, product_dir, folder / "images")
                if self.images is None:
                    self.images = LocalImages(self.root, self.run_dir / "cache", self.version)
                return self.images.process(source, product_dir, folder / "images", self.queue)
            # Changed existing final bytes invalidate dry-run stage reuse too.
            final_hashes = [(r, file_hash(product_dir / r)) for r in processed.get("images", []) + processed.get("description_images", [])]
            imgs, event = stages.run("images", [offer, source["source_url"], image_key, specification_hash(source),
                                                 self.version, self.dry_run, self.process_images, final_hashes], image_stage)
            audit["stages"]["images"] = event
            for name, value in imgs.get("specs", {}).items():
                if name in content["description_specs"] and content["description_specs"][name] != value:
                    self.queue.add(offer, "specification", "CONFLICTING_CONFIRMED_PARAMETER", {"field": name})
                else:
                    content["description_specs"][name] = value
            content["fingerprint"] = digest(dict(source=source, images=image_key, content=content, rules=self.version))
            save(folder / "prepared-product.json", content)
            from .runner_woocommerce import payloads
            if self.dry_run:
                # IDs and host below are synthetic and never passed to an HTTP client.
                media = {r["final_sha256"]: {"id": i + 1, "src": f"https://dry-run.invalid/{offer}/{r['final_sha256']}.webp"}
                         for i, r in enumerate(imgs["records"])}
                parent, variants, warnings = payloads(content, imgs["records"], media)
                save(folder / "dry-run-payload.json", dict(synthetic_media=True, parent=parent, variations=variants))
                audit.update(status="DRY_RUN_PASS", sku_count=len(variants), image_count=len(imgs["records"]),
                             publication_ready=False, publication="NOT_EXECUTED", rest_acceptance="NOT_EXECUTED", http_acceptance="NOT_EXECUTED")
                audit["warnings"].extend(warnings)
            else:
                final = self.store.upload(content, imgs, folder, draft=self.draft)
                audit.update(status=final["status"].upper(), product_id=final["product_id"], url=final["url"],
                             publication_ready=True, rest_acceptance="PASS", http_acceptance="PASS")
                audit["warnings"].extend(final["warnings"])
                entry = dict(product_id=final["product_id"], offer_id=offer, current_title=content["title"],
                             primary_keyword=content["seo"]["focus_keyword"], secondary_keywords=[],
                             search_intent="commercial product", updated_at=now())
                self.mapping = [m for m in self.mapping if str(m.get("offer_id")) != offer] + [entry]
                save(self.root / "data/keyword-map.json", self.mapping)
        except (ReviewRequired, ValueError) as exc:
            audit.update(status="REVIEW_REQUIRED", reason=str(exc), publication_ready=False)
            self.queue.add(offer, "product", str(exc))
        except Exception as exc:
            # Collector/HTTP errors can contain secrets/headers; log the type only.
            audit.update(status="FAIL", reason=type(exc).__name__, publication_ready=False)
            self.queue.add(offer, "execution", type(exc).__name__)
        audit.update(keyword_api_queries=self.planner.keyword_api_queries - queries,
                     woocommerce_writes=(self.store.write_count if self.store else 0) - writes_before,
                     keyword_cache_hits=self.planner.cache_hits - hits,
                     paid_api_cost=0.0 if self.planner.keyword_api_queries == queries else None,
                     paid_api_cost_note="No external model/paid API calls" if self.planner.keyword_api_queries == queries else "Invoice cost DATA_UNAVAILABLE",
                     processing_time=round(time.perf_counter() - started, 3), finished_at=now())
        save(folder / "audit.json", audit)
        return audit

    def run(self, tasks):
        # Drain every already-collected offer first: local/store work is never
        # stranded behind a subsequent human 1688 verification pause.
        ordered = sorted(tasks, key=lambda t: not self.source_path(t["offer_id"]).exists())
        results = []
        with exclusive_lock(self.root / "output/auto-runner/runner.lock"):
            for task in ordered:
                results.append(self.process(task))
                save(self.run_dir / "batch-audit.json", dict(complete=False, products=results))
        summary = dict(complete=True, dry_run=self.dry_run, products=results,
                       successes=sum(r["status"] in ("DRY_RUN_PASS", "PUBLISH", "DRAFT") for r in results),
                       review_required=sum(r["status"] == "REVIEW_REQUIRED" for r in results),
                       failures=sum(r["status"] == "FAIL" for r in results),
                       llm_calls=0, vision_calls=0, keyword_api_queries=self.planner.keyword_api_queries,
                       paid_api_cost=self.planner.cost, verification_count=len(self.verifications))
        save(self.run_dir / "batch-audit.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="1688 URL, XLSX, or explicit JSON task list")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--dry-run", action="store_true", help="Offline: no acquisition, API calls, store credentials, writes or publication")
    parser.add_argument("--process-images", action="store_true", help="Run provisioned local models even in dry-run instead of replaying saved image artifacts")
    parser.add_argument("--keyword-api", action="store_true", help="Allow Google Ads SDK queries for uncached terms; needs local credentials")
    parser.add_argument("--draft", action="store_true", help="Explicitly request draft; default verified new products publish")
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    tasks = read_tasks(args.input, args.start, args.end)
    runner = Runner(ROOT, dry_run=args.dry_run, process_images=args.process_images,
                    run_dir=None, keyword_api=args.keyword_api, draft=args.draft, poll_seconds=args.poll_seconds)
    if args.dry_run:
        from unittest.mock import patch
        # Enforced, not just a convention. Even accidental HTTP/SDK use fails.
        with patch("socket.socket", side_effect=RuntimeError("DRY_RUN_NETWORK_FORBIDDEN")):
            result = runner.run(tasks)
    else:
        result = runner.run(tasks)
    print(json.dumps({k: v for k, v in result.items() if k != "products"}, ensure_ascii=False))
    return 0 if not result["failures"] and not result["review_required"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
