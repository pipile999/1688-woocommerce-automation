"""Collect Excel rows 21-70 through the conservative 1688/OpenCLI queue.

The queue is serial, checkpoints after every offer, pauses on an X5/CAPTCHA/
login gate, keeps one named browser lease alive for manual intervention, and
resumes from the blocked offer after the persistent account is verified.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

try:
    from .batch20_collect_conservative import VerificationRequired, cli, collect_one
except ImportError:  # Preserve direct-script execution.
    from batch20_collect_conservative import VerificationRequired, cli, collect_one


SESSION_NAME = "batch50_1688_persistent"


PROTECTED = {
    "984680436841", "564665723647", "686860422447", "993417872006", "670587794806",
    "765561992235", "573461725446", "750383064542", "647045907437", "975071905867",
    "971789512000", "712505813291", "694636602872", "784587183745", "560619279229",
    "621218343539", "947833706702", "740616627112", "564448400011", "1009522330693",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_manifest(path: Path) -> list[dict]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("x:si", namespace):
                shared.append("".join(node.text or "" for node in item.iterfind(".//x:t", namespace)))
        sheet_root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    def cell_value(cell) -> str:
        cell_type = cell.get("t")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.iterfind(".//x:t", namespace))
        value = cell.findtext("x:v", default="", namespaces=namespace)
        return shared[int(value)] if cell_type == "s" and value else value

    rows: list[dict] = []
    for row in sheet_root.findall(".//x:sheetData/x:row", namespace):
        values = {re.sub(r"\d+$", "", cell.get("r", "")): cell_value(cell) for cell in row.findall("x:c", namespace)}
        try:
            sequence = int(float(values.get("A", "")))
        except (TypeError, ValueError):
            continue
        if not 21 <= sequence <= 70:
            continue
        source_url = values.get("C", "").strip()
        match = re.search(r"/offer/(\d+)\.html", source_url)
        if not match:
            raise RuntimeError(f"Row {sequence} has no valid 1688 offer URL")
        offer_id = match.group(1)
        if offer_id in PROTECTED:
            raise RuntimeError(f"Protected rows 1-20 overlap at row {sequence}: {offer_id}")
        rows.append({"sequence": sequence, "offer_id": offer_id, "source_url": source_url})
    rows.sort(key=lambda item: item["sequence"])
    if len(rows) != 50 or [x["sequence"] for x in rows] != list(range(21, 71)):
        raise RuntimeError("Excel rows 21-70 are incomplete or duplicated")
    ids = [x["offer_id"] for x in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Rows 21-70 contain duplicate Offer IDs")
    return rows


def original_is_complete(path: Path, offer_id: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        data.get("status") == "success"
        and str(data.get("offer_id")) == offer_id
        and bool(data.get("title"))
        and bool(data.get("skus"))
        and bool(data.get("raw_images"))
    )


def parse_json_output(result: subprocess.CompletedProcess[str]) -> object:
    if result.returncode:
        raise RuntimeError(((result.stdout or "") + "\n" + (result.stderr or "")).strip()[:1000])
    return json.loads(result.stdout)


def run_opencli_json(adapter: str, args: list[str], timeout: int = 120) -> object:
    result = subprocess.run(
        [adapter, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    return parse_json_output(result)


def run_opencli_text(adapter: str, args: list[str], timeout: int = 120) -> str:
    result = subprocess.run(
        [adapter, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    if result.returncode:
        raise RuntimeError(((result.stdout or "") + "\n" + (result.stderr or "")).strip()[:1000])
    return result.stdout or ""


def challenge_active(value: object) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower()
    return any(
        marker in text
        for marker in (
            "x5sec", "_____tmd_____", "验证码拦截", "x5 challenge", "x5 verification",
            "captcha", "滑块", "请登录", "重新登录", "login required", "安全验证",
        )
    )


def open_verification_window(adapter: str, offer_url: str) -> None:
    # Exactly one foreground navigation is made per verification event. Polling
    # below inspects local browser state and never reloads the 1688 page.
    match = re.search(r"/offer/(\d+)\.html", offer_url)
    if not match:
        raise RuntimeError("Verification URL has no valid Offer ID")
    # opencli may resolve to a Windows .cmd shim, so never pass untrusted query
    # separators to it. The canonical offer URL reaches the same challenge.
    canonical_url = f"https://detail.1688.com/offer/{match.group(1)}.html"
    run_opencli_text(
        adapter,
        ["browser", SESSION_NAME, "open", canonical_url, "--window", "foreground"],
        120,
    )


def check_whoami(adapter: str) -> dict | None:
    try:
        value = run_opencli_json(
            adapter,
            [
                "1688", "whoami", "-f", "json", "--window", "background",
                "--site-session", "persistent", "--keep-tab", "false",
            ],
            120,
        )
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if challenge_active(value):
        return None
    if isinstance(value, list):
        value = value[0] if len(value) == 1 else None
    return value if isinstance(value, dict) and value.get("logged_in") is True else None


def wait_for_manual_verification(adapter: str, offer_id: str, poll_seconds: int) -> dict:
    print(
        f"VERIFICATION_REQUIRED {offer_id}: headed Chrome is open; complete the slider/login manually.",
        flush=True,
    )
    while True:
        time.sleep(poll_seconds)
        try:
            state = run_opencli_text(adapter, ["browser", SESSION_NAME, "state"], 60)
        except (RuntimeError, subprocess.TimeoutExpired):
            continue
        if challenge_active(state):
            continue
        whoami = check_whoami(adapter)
        if whoami:
            print(f"VERIFICATION_PASSED {offer_id}: whoami confirmed; resuming queue.", flush=True)
            return {"logged_in": True, "site": whoami.get("site"), "user_id_present": bool(whoami.get("user_id"))}


def load_checkpoint(path: Path, manifest: list[dict], prior_metrics: Path) -> dict:
    if path.exists():
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
    else:
        checkpoint = {
            "version": 2,
            "browser_session": SESSION_NAME,
            "site_session": "persistent",
            "completed_offer_ids": [],
            "offer_results": {},
            "verification_events": [],
            "paused_for_verification": False,
            "current_offer_id": None,
            "created_at": utcnow(),
        }
        if prior_metrics.exists():
            prior = json.loads(prior_metrics.read_text(encoding="utf-8"))
            if prior.get("paused_for_verification") and prior.get("paused_at_offer"):
                blocked = next(
                    (x for x in prior.get("offers", []) if x.get("status") == "verification_required"), {}
                )
                checkpoint["verification_events"].append(
                    {
                        "verification_triggered_at": prior.get("finished_at") or prior.get("started_at"),
                        "offer_id": prior["paused_at_offer"],
                        "kind": blocked.get("kind", "unknown"),
                        "verification_count": 1,
                        "verification_duration_seconds": None,
                        "verification_passed_at": None,
                        "whoami_confirmed": False,
                        "resume_success": None,
                        "migrated_from_pre_checkpoint_run": True,
                    }
                )
                checkpoint["paused_for_verification"] = True
                checkpoint["current_offer_id"] = prior["paused_at_offer"]

    valid_ids = {x["offer_id"] for x in manifest}
    completed = {
        offer_id
        for offer_id in valid_ids
        if original_is_complete(Path("output") / offer_id / "original-product.json", offer_id)
    }
    completed.update(x for x in checkpoint.get("completed_offer_ids", []) if x in valid_ids)
    checkpoint["completed_offer_ids"] = sorted(completed, key=lambda x: next(i for i, e in enumerate(manifest) if e["offer_id"] == x))
    checkpoint["browser_session"] = SESSION_NAME
    checkpoint["site_session"] = "persistent"
    return checkpoint


def save_state(checkpoint_path: Path, metrics_path: Path, ready_path: Path, checkpoint: dict, manifest: list[dict], started: float) -> None:
    checkpoint["updated_at"] = utcnow()
    completed = checkpoint.get("completed_offer_ids", [])
    events = checkpoint.get("verification_events", [])
    completed_set = set(completed)
    for event in events:
        if event.get("whoami_confirmed") and event.get("offer_id") in completed_set:
            if event.get("resume_success") is False:
                event.setdefault("first_resume_attempt_success", False)
            event["resume_success"] = True
    resolved = [event for event in events if event.get("resume_success") is not None]
    successful_resumes = sum(event.get("resume_success") is True for event in resolved)
    metrics = {
        "updated_at": checkpoint["updated_at"],
        "queue_mode": "conservative_serial_manual_verification_resume",
        "browser_session": SESSION_NAME,
        "site_session": "persistent",
        "source_rows": "21-70",
        "success_count": len(completed),
        "verification_count": len(events),
        "average_products_per_verification": round(len(completed) / len(events), 3) if events else None,
        "verification_resume_success_rate": round(successful_resumes / len(resolved), 4) if resolved else None,
        "paused_for_verification": checkpoint.get("paused_for_verification", False),
        "current_offer_id": checkpoint.get("current_offer_id"),
        "failed_count": sum(v.get("status") == "failed" for v in checkpoint.get("offer_results", {}).values()),
        "not_completed_count": len(manifest) - len(completed),
        "verification_events": events,
        "elapsed_seconds_this_run": round(time.perf_counter() - started, 3),
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    ready_path.write_text(
        json.dumps(
            {
                "ready_offer_ids": completed,
                "original_product_files": [str(Path("output") / x / "original-product.json") for x in completed],
                "note": "Downstream local processing may consume completed offers while acquisition is paused.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", type=Path, default=Path("input-batch-21-70.xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--metrics-file", type=Path, default=Path("output/batch50-acquisition.json"))
    parser.add_argument("--manifest-file", type=Path, default=Path("output/batch50-manifest.json"))
    parser.add_argument("--checkpoint-file", type=Path, default=Path("output/batch50-checkpoint.json"))
    parser.add_argument("--ready-file", type=Path, default=Path("output/batch50-ready-for-processing.json"))
    parser.add_argument("--poll-seconds", type=int, default=12)
    args = parser.parse_args()

    manifest = read_manifest(args.excel)
    args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    adapter = cli()
    started = time.perf_counter()
    checkpoint = load_checkpoint(args.checkpoint_file, manifest, args.metrics_file)
    save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)

    pending_resume_event: int | None = None
    if checkpoint.get("paused_for_verification") and checkpoint.get("current_offer_id"):
        offer_id = checkpoint["current_offer_id"]
        entry = next(item for item in manifest if item["offer_id"] == offer_id)
        open_verification_window(adapter, entry["source_url"])
        whoami = wait_for_manual_verification(adapter, offer_id, args.poll_seconds)
        pending_resume_event = len(checkpoint["verification_events"]) - 1
        event = checkpoint["verification_events"][pending_resume_event]
        passed_at = datetime.now(timezone.utc)
        event["verification_passed_at"] = passed_at.isoformat()
        try:
            triggered = datetime.fromisoformat(event["verification_triggered_at"])
            event["verification_duration_seconds"] = round((passed_at - triggered).total_seconds(), 3)
        except (TypeError, ValueError):
            event["verification_duration_seconds"] = None
        event["whoami_confirmed"] = True
        event["whoami"] = whoami
        checkpoint["paused_for_verification"] = False
        save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)
        time.sleep(8)

    for position, entry in enumerate(manifest, 1):
        offer_id = entry["offer_id"]
        if offer_id in checkpoint["completed_offer_ids"]:
            continue
        original_path = args.output_dir / offer_id / "original-product.json"
        checkpoint["current_offer_id"] = offer_id
        print(f"[{position:02d}/50] collecting {offer_id}", flush=True)
        while True:
            try:
                result = collect_one(
                    adapter,
                    offer_id,
                    args.output_dir,
                    browser_session=SESSION_NAME,
                    keep_browser_session=True,
                    browser_window="background",
                    resume_partial=True,
                )
                product = json.loads(original_path.read_text(encoding="utf-8"))
                product["source_url"] = entry["source_url"]
                product["excel_sequence"] = entry["sequence"]
                original_path.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
                result["sequence"] = entry["sequence"]
                checkpoint["offer_results"][offer_id] = result
                checkpoint["completed_offer_ids"].append(offer_id)
                if pending_resume_event is not None:
                    checkpoint["verification_events"][pending_resume_event]["resume_success"] = True
                    pending_resume_event = None
                checkpoint["paused_for_verification"] = False
                checkpoint["current_offer_id"] = None
                save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)
                break
            except VerificationRequired as exc:
                if pending_resume_event is not None:
                    checkpoint["verification_events"][pending_resume_event]["first_resume_attempt_success"] = False
                event = {
                    "verification_triggered_at": utcnow(),
                    "offer_id": offer_id,
                    "kind": exc.kind,
                    "verification_count": len(checkpoint["verification_events"]) + 1,
                    "verification_duration_seconds": None,
                    "verification_passed_at": None,
                    "whoami_confirmed": False,
                    "resume_success": None,
                }
                checkpoint["verification_events"].append(event)
                pending_resume_event = len(checkpoint["verification_events"]) - 1
                checkpoint["paused_for_verification"] = True
                checkpoint["current_offer_id"] = offer_id
                checkpoint["offer_results"][offer_id] = {
                    "offer_id": offer_id,
                    "sequence": entry["sequence"],
                    "status": "verification_required",
                    "kind": exc.kind,
                }
                save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)
                open_verification_window(adapter, entry["source_url"])
                whoami = wait_for_manual_verification(adapter, offer_id, args.poll_seconds)
                passed_at = datetime.now(timezone.utc)
                event["verification_passed_at"] = passed_at.isoformat()
                event["verification_duration_seconds"] = round(
                    (passed_at - datetime.fromisoformat(event["verification_triggered_at"])).total_seconds(), 3
                )
                event["whoami_confirmed"] = True
                event["whoami"] = whoami
                checkpoint["paused_for_verification"] = False
                save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)
                time.sleep(8)
                continue
            except Exception as exc:  # isolated failure; continue with the next offer
                result = {
                    "offer_id": offer_id,
                    "sequence": entry["sequence"],
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                checkpoint["offer_results"][offer_id] = result
                if pending_resume_event is not None:
                    checkpoint["verification_events"][pending_resume_event]["first_resume_attempt_success"] = False
                    pending_resume_event = None
                checkpoint["current_offer_id"] = None
                save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)
                break

    checkpoint["finished_at"] = utcnow()
    checkpoint["current_offer_id"] = None
    save_state(args.checkpoint_file, args.metrics_file, args.ready_file, checkpoint, manifest, started)
    print(args.metrics_file.read_text(encoding="utf-8"), flush=True)


if __name__ == "__main__":
    raise SystemExit("HARD STOP: use the fixed site runner.py entry")
