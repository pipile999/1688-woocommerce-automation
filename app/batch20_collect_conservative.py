"""Conservative, failure-isolated acquisition queue for the 20-offer batch.

Structured public fields come from ``opencli 1688 item`` (the installed
1688-cli adapter), assets from ``opencli 1688 assets``, and complete SKU/spec
data from the authenticated page's captured skuSelectorBizModel response.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlparse

import requests


OFFERS = [
    "984680436841", "564665723647", "686860422447", "993417872006", "670587794806",
    "765561992235", "573461725446", "750383064542", "647045907437", "975071905867",
    "971789512000", "712505813291", "694636602872", "784587183745", "560619279229",
    "621218343539", "947833706702", "740616627112", "564448400011", "1009522330693",
]

PAGE_JS = r"""(()=>{
const d=window.context?.result?.data||{};
const f=d.description?.fields||{};
const g=d.gallery?.fields||{};
const t=d.productTitle?.fields||{};
const cpv=g.CpvEnhance||{};
return JSON.stringify({
 title:t.title||g.subject||document.title.replace(/\s*-\s*阿里巴巴\s*$/,''),
 detailUrl:f.detailUrl||null,
 categoryId:f.leafCategoryId||null,
 cpv:[...(cpv.decisionCpv||[]),...(cpv.normalCpv||[])],
 unit:t.unit||null,
 pageTitle:document.title,
 pageUrl:location.href
});})()"""


class VerificationRequired(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def cli() -> str:
    found = shutil.which("opencli")
    if found:
        return found
    candidate = Path(os.environ.get("APPDATA", "")) / "npm" / "opencli.cmd"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("opencli/1688-cli adapter is not installed")


def detect_verification(text: str) -> None:
    lowered = text.lower()
    if any(token in lowered for token in ("x5sec", "x5 challenge", "x5 verification", "x5安全验证")):
        raise VerificationRequired("x5", text[:500])
    if any(token in lowered for token in ("captcha", "验证码", "滑块", "verify you are", "安全验证")):
        raise VerificationRequired("captcha", text[:500])
    if any(token in lowered for token in (
        "login required", "auth_required", "请登录", "重新登录", "未登录",
        "完成 1688 登录/验证", "完成1688登录/验证", "共享 chrome 完成 1688 登录",
    )):
        raise VerificationRequired("login", text[:500])


def run_json(args: list[str], timeout: int = 120):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    detect_verification(combined)
    if result.returncode:
        raise RuntimeError(combined.strip()[:1000])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON OpenCLI output: {result.stdout[:500]}") from exc


def sale_price(value) -> str:
    return str((Decimal(str(value)) / Decimal("0.7") / Decimal("6.7")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def clean_url(value: str) -> str:
    value = html.unescape(value).replace("\\/", "/")
    return "https:" + value if value.startswith("//") else value


def source_suffix(url: str, content_type: str) -> str:
    mapping = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    key = content_type.split(";", 1)[0].lower()
    if key in mapping:
        return mapping[key]
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def download_images(urls: list[str], destination: Path) -> tuple[list[dict], list[dict]]:
    staging = destination.with_name(destination.name + "_staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    session = requests.Session()
    saved, failures = [], []
    for index, url in enumerate(urls, 1):
        try:
            response = session.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://detail.1688.com/"}, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            failures.append({"source_url": url, "error": f"{type(exc).__name__}: {exc}"})
            continue
        content_type = response.headers.get("content-type", "")
        if not content_type.lower().startswith("image/"):
            raise RuntimeError(f"Non-image asset: {url} ({content_type})")
        path = staging / f"{index:03d}{source_suffix(url, content_type)}"
        path.write_bytes(response.content)
        saved.append({"filename": path.name, "source_url": url, "bytes": len(response.content)})
    if not saved:
        raise RuntimeError("No product image could be downloaded")
    if destination.exists() and any(destination.iterdir()):
        backup = destination.with_name(f"{destination.name}_pre_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        destination.rename(backup)
    elif destination.exists():
        destination.rmdir()
    staging.rename(destination)
    return saved, failures


def unwrap_one(value, label: str) -> dict:
    if isinstance(value, list):
        if len(value) != 1:
            raise RuntimeError(f"{label} returned {len(value)} records")
        value = value[0]
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} returned an invalid record")
    return value


def capture_complete_skus(
    opencli: str,
    offer_id: str,
    url: str,
    *,
    session: str | None = None,
    keep_session: bool = False,
    window: str = "background",
) -> tuple[dict, dict]:
    session = session or f"batch20_{offer_id}"
    try:
        # A solved X5 page redirects to the target offer before collection
        # resumes. A normal timestamp query forces one fresh offer navigation
        # and SKU XHR without adding a second 1688 page request.
        navigation_url = f"{url}?_t={int(time.time() * 1000)}" if keep_session else url
        run_json([opencli, "browser", session, "open", navigation_url, "--window", window], 120)
        # The SKU endpoint is asynchronous. Inspecting the local network log a
        # few seconds later avoids misclassifying a still-loading page as a
        # permanent SKU failure; this does not issue another 1688 request.
        time.sleep(5)
        encoded = base64.b64encode(PAGE_JS.encode("utf-8")).decode("ascii")
        page = run_json([opencli, "browser", session, "eval", f'eval(atob("{encoded}"))'], 60)
        detect_verification(json.dumps(page, ensure_ascii=False))
        entries = []
        network = {}
        for _ in range(4):
            network = run_json([opencli, "browser", session, "network", "--since", "5m", "--filter", "skuSelectorBizModel"], 60)
            entries = network.get("entries") or []
            if entries:
                break
            time.sleep(3)
        if not entries:
            raise RuntimeError("skuSelectorBizModel network response was not captured")
        detail = run_json([opencli, "browser", session, "network", "--detail", entries[-1]["key"], "--max-body", "0"], 60)
        return page, detail
    finally:
        if not keep_session:
            subprocess.run([opencli, "browser", session, "close"], capture_output=True, timeout=30)


def collect_one(
    opencli: str,
    offer_id: str,
    output_root: Path,
    *,
    browser_session: str | None = None,
    keep_browser_session: bool = False,
    browser_window: str = "background",
    resume_partial: bool = False,
) -> dict:
    started = time.perf_counter()
    url = f"https://detail.1688.com/offer/{offer_id}.html"
    product_dir = output_root / offer_id
    product_dir.mkdir(parents=True, exist_ok=True)
    capture_dir = product_dir / "source_capture"
    capture_dir.mkdir(exist_ok=True)

    item_path = capture_dir / "1688-cli-item.json"
    assets_path = capture_dir / "opencli-assets.json"
    if resume_partial and item_path.exists():
        item = unwrap_one(json.loads(item_path.read_text(encoding="utf-8")), "cached 1688-cli item")
    else:
        item = unwrap_one(run_json([opencli, "1688", "item", url, "-f", "json", "--window", "background", "--site-session", "persistent", "--keep-tab", "false", "--trace", "retain-on-failure"]), "1688-cli item")
        item_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    if resume_partial and assets_path.exists():
        assets = unwrap_one(json.loads(assets_path.read_text(encoding="utf-8")), "cached OpenCLI assets")
    else:
        assets = unwrap_one(run_json([opencli, "1688", "assets", url, "-f", "json", "--window", "background", "--site-session", "persistent", "--keep-tab", "false", "--trace", "retain-on-failure"], 180), "OpenCLI assets")
        assets_path.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
    page, sku_capture = capture_complete_skus(
        opencli,
        offer_id,
        url,
        session=browser_session,
        keep_session=keep_browser_session,
        window=browser_window,
    )
    for name, value in (("browser-page.json", page), ("browser-sku.json", sku_capture)):
        (capture_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    model = sku_capture.get("body", {}).get("data", {}).get("skuSelectorBizModel") or {}
    selector = model.get("skuSelectorModel") or {}
    trade = selector.get("tradeModel") or {}
    sku_map = model.get("skuInfoMap") or model.get("originalSkuInfoMap") or {}
    sku_props = model.get("skuProps") or selector.get("skuPropsList") or []
    if not item.get("title") or not sku_map:
        raise RuntimeError("Required title or complete SKU map is missing")

    prop_names = [str(prop.get("prop") or f"Option {i + 1}") for i, prop in enumerate(sku_props)]
    value_images = {
        str(value.get("name")): clean_url(str(value.get("imageUrl")))
        for prop in sku_props for value in (prop.get("value") or [])
        if value.get("name") and value.get("imageUrl")
    }
    skus = []
    for key, record in sku_map.items():
        specs = [part.strip() for part in re.split(r">", html.unescape(str(record.get("specAttrs") or key))) if part.strip()]
        attributes = {(prop_names[i] if i < len(prop_names) else f"Option {i + 1}"): value for i, value in enumerate(specs)}
        source = record.get("discountPrice") or record.get("price")
        sku_id = record.get("skuId")
        if sku_id is None or source is None or not attributes:
            raise RuntimeError(f"Incomplete SKU entry {key}")
        spec_id = record.get("specId")
        skus.append({
            "sku": str(sku_id), "variation_id": str(sku_id),
            "spec_id": str(spec_id) if spec_id is not None else "unavailable",
            "source_spec_id": str(spec_id) if spec_id is not None else "unavailable",
            "attributes": attributes,
            "source_price": f"{Decimal(str(source)):.2f}", "sale_price": sale_price(source),
            "stock": record.get("canBookCount"), "image_url": value_images.get(specs[0]),
        })

    main_images = [clean_url(str(x)) for x in assets.get("main_images", []) if x]
    sku_images = [clean_url(str(x)) for x in assets.get("sku_images", []) if x]
    sku_images.extend(item["image_url"] for item in skus if item.get("image_url"))
    detail_images = [clean_url(str(x)) for x in assets.get("detail_images", []) if x]
    all_images = list(dict.fromkeys(main_images + sku_images + detail_images))
    if not all_images:
        raise RuntimeError("No product image was acquired")

    page_cpv = page.get("cpv") or []
    cpv = [{"name": str(x.get("name")), "values": [str(v) for v in x.get("values", [])]} for x in page_cpv if x.get("name") and x.get("values")]
    visible = [{"name": str(x.get("key")), "values": [str(x.get("value"))]} for x in item.get("visible_attributes", []) if x.get("key") and x.get("value")]
    known = {x["name"] for x in cpv}
    cpv.extend(x for x in visible if x["name"] not in known)
    product = {
        "status": "success", "offer_id": offer_id, "model": f"Model: {offer_id}", "source_url": url,
        "title": item["title"], "description": {"type": "image_only", "detail_images": detail_images},
        "attributes": {"normalCpv": cpv}, "price_tiers": item.get("price_tiers", []),
        "minimum_order_quantity": item.get("moq_value") or trade.get("beginAmount"), "unit": item.get("unit") or page.get("unit"),
        "skus": skus, "main_images": main_images, "detail_images": detail_images, "images": all_images,
        "variation_color_images": value_images, "package": {}, "source_category_id": page.get("categoryId"),
        "optional_field_warnings": [], "missing_fields": [], "woocommerce_uploaded": False,
        "source_collectors": {"structured_data": "1688-cli item", "assets": "OpenCLI 1688 assets", "sku_completion": "authenticated browser network capture"},
        "collected_at": utcnow(),
    }
    if any(x["spec_id"] == "unavailable" for x in skus):
        product["optional_field_warnings"].append({"field": "source_spec_id", "status": "WARNING", "reason": "source did not expose a distinct spec ID"})
    product["raw_images"], image_download_failures = download_images(all_images, product_dir / "raw_images")
    if image_download_failures:
        product["optional_field_warnings"].append({"field": "source_images", "status": "WARNING", "reason": f"{len(image_download_failures)} source asset(s) returned an HTTP error and were skipped"})
        (capture_dir / "image-download-warnings.json").write_text(json.dumps(image_download_failures, ensure_ascii=False, indent=2), encoding="utf-8")
    (product_dir / "original-product.json").write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"offer_id": offer_id, "status": "success", "sku_count": len(skus), "image_count": len(all_images), "elapsed_seconds": round(time.perf_counter() - started, 3)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--metrics-file", type=Path, default=Path("output/batch20-acquisition.json"))
    parser.add_argument("--start-at", choices=OFFERS)
    parser.add_argument("--offer-id", action="append", choices=OFFERS)
    args = parser.parse_args()
    opencli = cli()
    started = time.perf_counter()
    report = {"started_at": utcnow(), "queue_mode": "conservative_serial", "offers": [], "x5_count": 0, "captcha_or_login_count": 0, "paused_for_verification": False}
    start_index = OFFERS.index(args.start_at) if args.start_at else 0
    selected_offers = args.offer_id or OFFERS[start_index:]
    for offer_id in selected_offers:
        index = OFFERS.index(offer_id) + 1
        print(f"[{index:02d}/20] collecting {offer_id}", flush=True)
        try:
            result = collect_one(opencli, offer_id, args.output_dir)
        except VerificationRequired as exc:
            if exc.kind == "x5": report["x5_count"] += 1
            else: report["captcha_or_login_count"] += 1
            result = {"offer_id": offer_id, "status": "verification_required", "kind": exc.kind, "error": str(exc)}
            report["offers"].append(result)
            report["paused_for_verification"] = True
            report["paused_at_offer"] = offer_id
            break
        except Exception as exc:
            result = {"offer_id": offer_id, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        report["offers"].append(result)
        args.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        args.metrics_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["finished_at"] = utcnow()
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    report["success_count"] = sum(x["status"] == "success" for x in report["offers"])
    report["failure_count"] = sum(x["status"] in {"failed", "verification_required"} for x in report["offers"])
    report["not_attempted_count"] = len(selected_offers) - len(report["offers"])
    args.metrics_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
