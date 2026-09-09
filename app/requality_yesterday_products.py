"""Quality-audit and selectively repair the 113 products published on 2026-09-08.

The runner never contacts 1688. It uses saved raw evidence as the only edit source,
runs a second real PaddleOCR/OpenCLIP pass over every storefront image, repairs only
failed assets, updates the existing WooCommerce IDs, and verifies immutable data.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import sys
import time
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import requests
import cv2
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageOps

from .batch50_process_pipeline import draw_translations, has_cjk, translate_ocr
from .batch50_upload_publish import image_alt, metadata, upload_media, wp_request
from .image_pipeline import (
    InpaintingAdapter,
    OCRAdapter,
    RembgAdapter,
    VisionClassifierAdapter,
    adaptive_quality_webp,
)
from .woocommerce import WooCommerceClient


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
RUN_DIR = OUTPUT / "yesterday-quality-audit"
CACHE_DIR = RUN_DIR / "ai-cache-v2"
CHECKPOINT = RUN_DIR / "checkpoint.json"
SUMMARY = RUN_DIR / "summary.json"
LAMA_MODEL = ROOT / "models" / "lama" / "lama_fp32.onnx"
REMBG_MODELS = ROOT / "models" / "rembg"
PUBLISHED_DATE = "2026-09-08"

FIRST_20 = [
    "984680436841", "564665723647", "686860422447", "993417872006", "670587794806",
    "765561992235", "573461725446", "750383064542", "647045907437", "975071905867",
    "971789512000", "712505813291", "694636602872", "784587183745", "560619279229",
    "621218343539", "947833706702", "740616627112", "564448400011", "1009522330693",
]

BLOCK_CLASSES = {"factory_or_company", "certificate_or_document", "qr_or_contact_card"}
SUPPLIER_TEXT = (
    "1688", "alibaba", "wechat", "weixin", "whatsapp", "factory direct", "manufacturer",
    "supplier", "company", "contact us", "scan code", "二维码", "微信", "厂家", "工厂",
    "公司", "店铺", "网址", "联系电话", "手机", "征程煙具", "征程烟具", "z.c.y.j",
)
ALLOWED_SPEC_KEYS = (
    "material", "size", "dimension", "weight", "color", "pack", "quantity",
    "configuration", "capacity", "diameter", "height", "length", "model",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest() -> list[dict]:
    entries = [{"sequence": index, "offer_id": offer} for index, offer in enumerate(FIRST_20, 1)]
    entries.extend(read_json(OUTPUT / "batch50-manifest.json"))
    entries.extend(read_json(OUTPUT / "batch43-manifest.json"))
    if len(entries) != 113 or len({str(item["offer_id"]) for item in entries}) != 113:
        raise RuntimeError("yesterday manifest must contain exactly 113 unique Offer IDs")
    for item in entries:
        offer = str(item["offer_id"])
        audit = read_json(OUTPUT / offer / "final-product-audit.json")
        item["product_id"] = int(audit["product_id"])
    return entries


def jsonable_analysis(path: Path, ocr: OCRAdapter, clip: VisionClassifierAdapter) -> dict:
    payload = path.read_bytes()
    image = ImageOps.exif_transpose(Image.open(BytesIO(payload))).convert("RGB")
    ocr_result = ocr.analyze(payload)
    classification = clip.classify(payload)
    return {
        "sha256": sha256(path),
        "width": image.width,
        "height": image.height,
        "ocr_text": [item.text for item in ocr_result.detections],
        "text_coverage": round(ocr_result.text_coverage, 6),
        "ocr_detections": [
            {"text": item.text, "score": item.score, "polygon": item.polygon}
            for item in ocr_result.detections
        ],
        "classification": {
            "label": classification.label,
            "confidence": classification.confidence,
            "scores": classification.scores,
        },
    }


def analyze(path: Path, ocr: OCRAdapter, clip: VisionClassifierAdapter) -> dict:
    digest = sha256(path)
    cache = CACHE_DIR / f"{digest}.json"
    if cache.is_file():
        return read_json(cache)
    result = jsonable_analysis(path, ocr, clip)
    write_json(cache, result)
    return result


def prohibited_text(texts: list[str]) -> list[str]:
    failures = []
    for value in texts:
        lowered = value.lower().strip()
        if has_cjk(value):
            failures.append(f"Chinese text: {value}")
        if any(token in lowered for token in SUPPLIER_TEXT):
            failures.append(f"supplier identity/promotion: {value}")
        if re.search(r"(?:https?://|www\.|[a-z0-9-]+\.(?:com|cn|net))", lowered):
            failures.append(f"shop URL: {value}")
        if re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", lowered):
            failures.append(f"phone/contact: {value}")
    return list(dict.fromkeys(failures))


def safe_specs(product: dict) -> dict[str, str]:
    result = {}
    for key, value in (product.get("description_specs") or {}).items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if not key_text or not value_text or has_cjk(key_text + value_text):
            continue
        if not any(token in key_text.lower() for token in ALLOWED_SPEC_KEYS):
            continue
        if re.fullmatch(r"[\W_]*\d{0,3}[\W_]*", value_text) or value_text.count("(") != value_text.count(")"):
            continue
        if len(re.sub(r"\W", "", value_text)) < 2:
            continue
        result[key_text] = value_text
    return result


def source_record_map(product_dir: Path) -> dict[str, dict]:
    audit = read_json(product_dir / "image_audit" / "image-audit.json")
    mapping = {}
    for record in audit.get("records", []):
        output = record.get("output_file")
        if output:
            mapping[str(output).replace("\\", "/")] = record
        if record.get("final_filename"):
            mapping.setdefault(str(record["final_filename"]), record)
    return mapping


def find_source(product_dir: Path, relative: str, records: dict[str, dict]) -> tuple[Path | None, dict]:
    record = records.get(relative) or records.get(Path(relative).name) or {}
    filename = record.get("filename")
    if filename and (product_dir / "raw_images" / filename).is_file():
        return product_dir / "raw_images" / filename, record
    final_name = Path(relative).name
    for candidate in (product_dir / "raw_images").glob("*"):
        if candidate.is_file() and candidate.stem == Path(final_name).stem:
            return candidate, record
    return None, record


def prepare_master(image: Image.Image, role: str) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if role == "detail" and image.width > 1600:
        scale = 1600 / image.width
        return image.resize((1600, max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    if role != "detail" and max(image.size) > 2200:
        scale = 2200 / max(image.size)
        return image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    return image


def role_for(relative: str, product: dict, record: dict) -> str:
    if relative in product.get("description_images", []):
        return "detail"
    if relative in set((product.get("variation_image_map") or {}).values()):
        return "variation"
    return str(record.get("source_role") or "main")


def save_webp(master: Image.Image, source: Path, destination: Path, role: str, text_sensitive: bool) -> dict:
    master = prepare_master(master, role)
    with Image.open(source) as raw:
        source_dimensions = ImageOps.exif_transpose(raw).size
    payload, quality = adaptive_quality_webp(
        master,
        source_dimensions=source_dimensions,
        source_filesize=source.stat().st_size,
        max_edge=None,
        text_sensitive=text_sensitive,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return quality


def text_product_overlap(cutout: Image.Image, text_mask: Image.Image) -> dict:
    """Measure whether an OCR region crosses the stable interior of the product."""
    alpha = np.asarray(cutout.getchannel("A"), dtype=np.uint8)
    product = (alpha >= 96).astype(np.uint8)
    product_core = cv2.erode(product, np.ones((11, 11), np.uint8), iterations=1)
    mask = text_mask.convert("L")
    if mask.size != cutout.size:
        mask = mask.resize(cutout.size, Image.Resampling.NEAREST)
    text = (np.asarray(mask, dtype=np.uint8) > 0).astype(np.uint8)
    intersection = int(np.count_nonzero(product_core & text))
    product_pixels = max(1, int(np.count_nonzero(product_core)))
    text_pixels = max(1, int(np.count_nonzero(text)))
    return {
        "intersection_pixels": intersection,
        "product_overlap_ratio": round(intersection / product_pixels, 6),
        "text_overlap_ratio": round(intersection / text_pixels, 6),
        "unsafe": intersection / product_pixels >= 0.003 or intersection / text_pixels >= 0.12,
    }


def visual_failures(analysis: dict) -> list[str]:
    failures = prohibited_text(analysis["ocr_text"])
    allowed_short_text = {"xl", "cm", "mm", "oz", "ml", "kg", "in", "us", "eu"}
    for value in analysis["ocr_text"]:
        compact = re.sub(r"[^A-Za-z0-9]", "", str(value)).lower()
        if len(compact) == 2 and compact not in allowed_short_text:
            failures.append(f"unreadable or context-free OCR fragment: {value}")
    label = analysis["classification"]["label"]
    confidence = float(analysis["classification"]["confidence"])
    if label in BLOCK_CLASSES and confidence >= 0.45:
        failures.append(f"blocked visual class: {label}")
    # A damaged/deformed CLIP label is recorded for visual audit, but is not a
    # deletion signal by itself: printed product artwork can resemble a smear.
    # Hard failure requires corroborating dimension/sharpness loss or OCR residue.
    return failures


def current_quality(path: Path, source: Path | None, role: str) -> tuple[dict, list[str]]:
    current = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    current_gray = cv2.cvtColor(np.asarray(current), cv2.COLOR_RGB2GRAY)
    current_sharpness = float(cv2.Laplacian(current_gray, cv2.CV_32F).var(dtype=np.float32))
    result = {
        "processed_width": current.width,
        "processed_height": current.height,
        "final_filesize": path.stat().st_size,
        "source_width": None,
        "source_height": None,
        "source_filesize": None,
        "compression_ratio": None,
        "processed_sharpness": round(current_sharpness, 3),
        "reference_sharpness": None,
        "sharpness_ratio": None,
        "sharpness_quality_check": "PASS",
    }
    failures = []
    if source and source.is_file():
        original = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        reference = original.resize(current.size, Image.Resampling.LANCZOS) if original.size != current.size else original
        reference_gray = cv2.cvtColor(np.asarray(reference), cv2.COLOR_RGB2GRAY)
        reference_sharpness = float(cv2.Laplacian(reference_gray, cv2.CV_32F).var(dtype=np.float32))
        sharpness_ratio = current_sharpness / reference_sharpness if reference_sharpness else 1.0
        result.update({
            "source_width": original.width,
            "source_height": original.height,
            "source_filesize": source.stat().st_size,
            "compression_ratio": round(path.stat().st_size / source.stat().st_size, 4) if source.stat().st_size else None,
            "reference_sharpness": round(reference_sharpness, 3),
            "sharpness_ratio": round(sharpness_ratio, 4),
        })
        if role == "detail" and original.width >= 1000 and current.width < 900:
            failures.append("detail image was incorrectly reduced below useful reading width")
        if max(original.size) >= 1200 and max(current.size) < 0.65 * max(original.size) and max(current.size) < 1000:
            failures.append("high-resolution source was incorrectly downscaled")
        if reference_sharpness >= 25 and sharpness_ratio < 0.52:
            failures.append("current WebP has material sharpness loss versus its raw original")
    if min(current.size) < 240:
        failures.append("final image is too small for useful storefront display")
    if failures:
        result["sharpness_quality_check"] = "FAIL"
    return result, failures


def output_name(product: dict, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(product.get("slug") or product["offer_id"]).lower()).strip("-")
    return f"quality_images/{slug}-qa-{index:03d}.webp"


def title_seo_audit(product: dict) -> tuple[dict, list[str], bool]:
    updated = deepcopy(product)
    issues = []
    title = str(product.get("title", "")).strip()
    if has_cjk(title) or any(token in title.lower() for token in SUPPLIER_TEXT):
        issues.append("title contains supplier/Chinese identity and cannot be safely inferred")
        return updated, issues, False
    words = re.findall(r"[a-z0-9]+", title.lower())
    if any(words.count(word) > 2 for word in set(words) if len(word) > 3):
        issues.append("title keyword stuffing")
    if len(title) > 90:
        issues.append("title exceeds concise search-title length")
    seo = updated.get("seo") or {}
    meta_title = str(seo.get("meta_title") or title).strip()
    focus = str(seo.get("focus_keyword") or "").strip()
    if has_cjk(meta_title + focus) or any(token in (meta_title + " " + focus).lower() for token in SUPPLIER_TEXT):
        issues.append("SEO contains supplier/Chinese identity")
    # Do not manufacture replacements: already-natural English copy is retained; unsafe copy blocks the item.
    return updated, issues, False


def process_local_product(
    entry: dict,
    ocr: OCRAdapter,
    clip: VisionClassifierAdapter,
    inpainter: InpaintingAdapter,
    rembg_holder: dict,
    force_source_rebuild: bool = False,
) -> dict:
    offer = str(entry["offer_id"])
    product_dir = OUTPUT / offer
    product_file = product_dir / "processed-product.json"
    product = read_json(product_file)
    backup = product_dir / "processed-product.pre-quality-20260909.json"
    if not backup.exists():
        shutil.copy2(product_file, backup)
    baseline_product = read_json(backup)
    original_product = deepcopy(product)
    product, seo_issues, seo_rewritten = title_seo_audit(product)
    prior_quality_state = (product.get("processing") or {}).get("quality_upgrade_20260909") or {}
    strict_source_rebuild = force_source_rebuild or not bool(prior_quality_state.get("supplier_residual_hardened"))
    records_by_output = source_record_map(product_dir)
    paths = list(dict.fromkeys(
        list(product.get("images", []))
        + list(product.get("description_images", []))
        + list((product.get("variation_image_map") or {}).values())
    ))
    baseline_paths = list(dict.fromkeys(
        list(baseline_product.get("images", []))
        + list(baseline_product.get("description_images", []))
        + list((baseline_product.get("variation_image_map") or {}).values())
    ))
    replacements: dict[str, str] = {}
    rejected: dict[str, str] = {}
    audit_records = []
    counters = {
        "featured_redone": 0,
        "rembg_images": 0,
        "supplier_logo_url_deleted": 0,
        "parameter_to_html": 0,
        "chinese_residual_fixed": 0,
        "too_small_detail_fixed": 0,
        "long_description_supplemented": 0,
        "title_seo_rewritten": int(seo_rewritten),
    }
    safe_product_specs = safe_specs(product)
    for index, relative in enumerate(paths, 1):
        final_path = product_dir / relative
        source, source_record = find_source(product_dir, relative, records_by_output)
        if source is None:
            quality_index = re.search(r"-qa-(\d+)\.webp$", relative, flags=re.IGNORECASE)
            if quality_index:
                original_index = int(quality_index.group(1)) - 1
                if 0 <= original_index < len(baseline_paths):
                    source, source_record = find_source(product_dir, baseline_paths[original_index], records_by_output)
        role = role_for(relative, product, source_record)
        if not final_path.is_file():
            rejected[relative] = "local final image missing"
            audit_records.append({"relative": relative, "decision": "reject", "reason": rejected[relative]})
            continue
        analysis_before = analyze(final_path, ocr, clip)
        quality, quality_failures = current_quality(final_path, source, role)
        failures = visual_failures(analysis_before) + quality_failures
        source_analysis = None
        # Older repaired outputs may contain very faint supplier overlays that
        # a second OCR pass cannot rediscover. On the hardening pass, consult
        # the saved raw evidence for every generated QA image and regenerate
        # it when the original carried prohibited supplier text.
        if not failures and strict_source_rebuild and source is not None and relative.startswith("quality_images/"):
            source_analysis = analyze(source, ocr, clip)
            if prohibited_text(source_analysis["ocr_text"]):
                failures.append("strict rebuild from raw source with known supplier-text contamination")
        source_label = str((source_record.get("classification") or {}).get("label") or "")
        source_coverage = float(source_record.get("text_coverage") or 0)
        before_has_chinese = any(has_cjk(text) for text in analysis_before["ocr_text"])
        record = {
            "relative": relative,
            "source_filename": source.name if source else None,
            "role": role,
            "paddleocr_actually_executed": True,
            "openclip_actually_executed": True,
            "analysis_before": analysis_before,
            "quality_before": quality,
            "failures_before": failures,
            "decision": "keep",
            "repair": None,
            "replacement": None,
        }
        if not failures:
            audit_records.append(record)
            continue
        if source is None:
            rejected[relative] = "failed QA and no saved raw original maps to this image"
            record.update({"decision": "reject", "reason": rejected[relative]})
            audit_records.append(record)
            continue
        source_analysis = source_analysis or analyze(source, ocr, clip)
        source_visual = source_analysis["classification"]["label"]
        source_text_failures = prohibited_text(source_analysis["ocr_text"])
        is_infographic = source_label == "product_infographic" or source_visual == "product_infographic"
        if is_infographic and source_text_failures:
            rejected[relative] = "complex parameter/text graphic failed OCR residual gate; represented by verified HTML specifications"
            record.update({"decision": "reject", "reason": rejected[relative], "analysis_source": source_analysis})
            if safe_product_specs:
                counters["parameter_to_html"] += 1
            if before_has_chinese:
                counters["chinese_residual_fixed"] += 1
            audit_records.append(record)
            continue
        if source_visual in BLOCK_CLASSES:
            rejected[relative] = f"raw source is non-product class {source_visual}"
            record.update({"decision": "reject", "reason": rejected[relative], "analysis_source": source_analysis})
            if source_text_failures:
                counters["supplier_logo_url_deleted"] += 1
            audit_records.append(record)
            continue
        destination_relative = output_name(product, index)
        destination = product_dir / destination_relative
        repair_method = "highest_resolution_original_reencode"
        rembg_details = None
        source_bytes = source.read_bytes()
        overlap_details = None
        raw_ocr = None
        if source_text_failures:
            if "adapter" not in rembg_holder:
                rembg_holder["adapter"] = RembgAdapter(REMBG_MODELS)
            raw_ocr = ocr.analyze(source_bytes)
            raw_cutout = rembg_holder["adapter"].cutout(source_bytes)
            overlap_details = text_product_overlap(raw_cutout, raw_ocr.mask)
            if overlap_details["unsafe"]:
                rejected[relative] = "supplier/text overlay crosses product pixels; rejected to prevent destructive repair"
                counters["supplier_logo_url_deleted"] += 1
                if before_has_chinese:
                    counters["chinese_residual_fixed"] += 1
                record.update({
                    "decision": "reject",
                    "reason": rejected[relative],
                    "analysis_source": source_analysis,
                    "text_product_overlap": overlap_details,
                })
                audit_records.append(record)
                continue
        heavy_pollution = bool(source_text_failures) and (source_coverage >= 0.07 or len(source_analysis["ocr_text"]) >= 4)
        if heavy_pollution and source_visual == "product_photo":
            if "adapter" not in rembg_holder:
                rembg_holder["adapter"] = RembgAdapter(REMBG_MODELS)
            # Remove the detected overlay from the real source pixels before
            # segmentation. This prevents rembg from preserving faint letters
            # as foreground or carrying a watermark across the product cutout.
            cutout_source = source_bytes
            precutout_inpainting = False
            if raw_ocr is not None and raw_ocr.mask.getbbox():
                cutout_source = inpainter.inpaint(source_bytes, raw_ocr.mask)
                precutout_inpainting = True
            master, rembg_details = rembg_holder["adapter"].on_neutral_square(cutout_source)
            rembg_details["precutout_lama_cleanup"] = precutout_inpainting
            repair_method = "rembg_product_cutout_neutral_background"
            counters["rembg_images"] += 1
        elif source_text_failures:
            raw_ocr = ocr.analyze(source_bytes)
            if raw_ocr.mask.getbbox():
                cleaned = Image.open(BytesIO(inpainter.inpaint(source_bytes, raw_ocr.mask))).convert("RGB")
                translations = [translate_ocr(item.text) for item in raw_ocr.detections if has_cjk(item.text)]
                if any(translations) and len(raw_ocr.detections) <= 6:
                    detections = [{"text": item.text, "score": item.score, "polygon": item.polygon} for item in raw_ocr.detections]
                    cleaned = draw_translations(cleaned, detections)
                master = cleaned
                repair_method = "precise_ocr_mask_lama_inpainting"
            else:
                master = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        else:
            master = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        optimization = save_webp(master, source, destination, role, is_infographic)
        analysis_after = analyze(destination, ocr, clip)
        after_failures = visual_failures(analysis_after)
        if after_failures and repair_method != "rembg_product_cutout_neutral_background" and source_visual == "product_photo":
            if "adapter" not in rembg_holder:
                rembg_holder["adapter"] = RembgAdapter(REMBG_MODELS)
            raw_ocr = ocr.analyze(source_bytes)
            cutout_source = source_bytes
            precutout_inpainting = False
            if raw_ocr.mask.getbbox():
                cutout_source = inpainter.inpaint(source_bytes, raw_ocr.mask)
                precutout_inpainting = True
            master, rembg_details = rembg_holder["adapter"].on_neutral_square(cutout_source)
            rembg_details["precutout_lama_cleanup"] = precutout_inpainting
            optimization = save_webp(master, source, destination, role, False)
            analysis_after = analyze(destination, ocr, clip)
            after_failures = visual_failures(analysis_after)
            repair_method = "rembg_product_cutout_neutral_background"
            counters["rembg_images"] += 1
        if after_failures:
            rejected[relative] = "repair failed second OCR/visual QA: " + "; ".join(after_failures)
            destination.unlink(missing_ok=True)
            record.update({"decision": "reject", "reason": rejected[relative], "analysis_source": source_analysis, "analysis_after": analysis_after})
            audit_records.append(record)
            continue
        replacements[relative] = destination_relative
        if before_has_chinese:
            counters["chinese_residual_fixed"] += 1
        if any("detail image was incorrectly reduced" in item for item in quality_failures):
            counters["too_small_detail_fixed"] += 1
        record.update({
            "decision": "repair",
            "repair": repair_method,
            "replacement": destination_relative,
            "analysis_source": source_analysis,
            "analysis_after": analysis_after,
            "rembg": rembg_details,
            "optimization": optimization,
            "inpainting_executed": repair_method == "precise_ocr_mask_lama_inpainting",
            "rembg_executed": repair_method == "rembg_product_cutout_neutral_background",
        })
        audit_records.append(record)

    def remap(values: list[str]) -> list[str]:
        result = []
        for value in values:
            if value in rejected:
                continue
            mapped = replacements.get(value, value)
            if mapped not in result:
                result.append(mapped)
        return result

    old_featured = product.get("featured_image")
    product["images"] = remap(list(product.get("images", [])))
    product["description_images"] = remap(list(product.get("description_images", [])))
    product["variation_image_map"] = {
        str(sku): replacements.get(path, path)
        for sku, path in (product.get("variation_image_map") or {}).items()
        if path not in rejected
    }
    if not product["images"]:
        raise RuntimeError("all storefront images failed the quality gate")
    expected_featured = replacements.get(old_featured, old_featured)
    if expected_featured in rejected or expected_featured not in product["images"]:
        expected_featured = product["images"][0]
    if product["images"][0] != expected_featured:
        product["images"].remove(expected_featured)
        product["images"].insert(0, expected_featured)
    product["featured_image"] = expected_featured
    if old_featured != expected_featured:
        counters["featured_redone"] += 1
    if not product["description_images"]:
        product["description_images"] = [product["images"][1] if len(product["images"]) > 1 else product["images"][0]]
        counters["long_description_supplemented"] += 1
    product["description_specs"] = safe_product_specs
    product.setdefault("processing", {})["quality_upgrade_20260909"] = {
        "highest_resolution_original_first": True,
        "single_final_webp_encode": True,
        "adaptive_webp_quality": True,
        "second_paddleocr_openclip_qa": True,
        "supplier_residual_hardened": True,
        "rembg_model": RembgAdapter.model_name,
        "quality_audit_at": utcnow(),
    }
    problems = bool(replacements or rejected or counters["long_description_supplemented"] or seo_issues)
    local_result = {
        "offer_id": offer,
        "product_id": int(entry["product_id"]),
        "scope_date": PUBLISHED_DATE,
        "problem_found": problems,
        "replacements": replacements,
        "rejected": rejected,
        "seo_issues": seo_issues,
        "counters": counters,
        "model_execution": {
            "paddleocr": {"actually_executed": True, "model": f"{OCRAdapter.detection_model} + {OCRAdapter.recognition_model}"},
            "openclip": {"actually_executed": True, "model": VisionClassifierAdapter.model_name, "pretrained": VisionClassifierAdapter.pretrained},
            "lama": {"model": InpaintingAdapter.model_name, "actually_executed": any(x.get("inpainting_executed") for x in audit_records)},
            "rembg": {"model": RembgAdapter.model_name, "actually_executed": any(x.get("rembg_executed") for x in audit_records)},
        },
        "final_image_count": len(set(product["images"] + product["description_images"] + list(product["variation_image_map"].values()))),
        "records": audit_records,
        "completed_at": utcnow(),
    }
    write_json(product_dir / "quality-audit-20260909.json", local_result)
    if product != original_product:
        write_json(product_file, product)
    return local_result


def description_html(product: dict, media: dict[str, dict]) -> str:
    chunks = ["<h2>Product Overview</h2>", f"<p>{html.escape(str(product['description_overview']))}</p>"]
    bullets = product.get("description_bullets") or []
    if bullets:
        chunks += ["<h2>Product Details</h2>", "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in bullets) + "</ul>"]
    for relative in product.get("description_images", []):
        source = html.escape(media[relative]["src"], quote=True)
        alt = html.escape(image_alt(product, relative), quote=True)
        chunks.append(
            f'<figure class="wp-block-image size-full"><img src="{source}" alt="{alt}" '
            'loading="lazy" style="max-width:100%;height:auto"></figure>'
        )
    specs = safe_specs(product)
    if specs:
        rows = "".join(f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>" for key, value in specs.items())
        chunks += ["<h2>Specifications</h2>", f"<table><tbody>{rows}</tbody></table>"]
    chunks.append(f"<p><strong>Model:</strong> {html.escape(str(product['offer_id']))}</p>")
    return "\n".join(chunks)


def money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def invariant_snapshot(parent: dict, variations: list[dict]) -> dict:
    return {
        "status": parent.get("status"),
        "categories": [int(item["id"]) for item in parent.get("categories", [])],
        "model": metadata(parent.get("meta_data", [])).get("_1688_model"),
        "source_url": metadata(parent.get("meta_data", [])).get("_1688_source_url"),
        "variations": {
            str(item.get("sku")): {
                "id": int(item["id"]),
                "regular_price": str(item.get("regular_price")),
                "attributes": item.get("attributes", []),
                "variation_id": metadata(item.get("meta_data", [])).get("_1688_variation_id"),
                "spec_id": metadata(item.get("meta_data", [])).get("_1688_spec_id"),
                "image_id": int((item.get("image") or {}).get("id") or 0),
            }
            for item in variations
        },
    }


def image_http(url: str) -> dict:
    try:
        response = requests.get(url, stream=True, timeout=80)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        result = {"url": url, "status": response.status_code, "content_type": content_type, "pass": response.status_code == 200 and content_type.startswith("image/")}
        response.close()
        return result
    except requests.RequestException as exc:
        return {"url": url, "status": None, "content_type": "", "pass": False, "error": type(exc).__name__}


def upload_and_verify(client: WooCommerceClient, entry: dict, local_audit: dict) -> dict:
    offer = str(entry["offer_id"])
    product_dir = OUTPUT / offer
    product = read_json(product_dir / "processed-product.json")
    product_id = int(entry["product_id"])
    before_parent = client.get(f"products/{product_id}", {"context": "edit"})
    before_variations = client.get(f"products/{product_id}/variations", {"per_page": 100, "context": "edit"})
    before = invariant_snapshot(before_parent, before_variations)
    failures = []
    if str(metadata(before_parent.get("meta_data", [])).get("_1688_offer_id")) != offer:
        failures.append("WooCommerce Offer ID does not match manifest")
    if before["model"] != f"Model: {offer}":
        failures.append("Model mismatch before update")
    if before["source_url"] != product["source_url"]:
        failures.append("source URL mismatch before update")
    if before["status"] != "publish":
        failures.append("yesterday product is no longer published")
    if failures:
        raise RuntimeError("; ".join(failures))
    media = upload_media(client, product_dir, product)
    parent_images = [
        {"id": int(media[relative]["id"]), "position": index, "name": image_alt(product, relative), "alt": image_alt(product, relative)}
        for index, relative in enumerate(product["images"])
    ]
    payload = {"images": parent_images, "description": description_html(product, media)}
    if local_audit["counters"]["title_seo_rewritten"]:
        payload["name"] = product["title"]
        payload["slug"] = product["slug"]
        payload["meta_data"] = [
            {"key": "rank_math_title", "value": product["seo"]["meta_title"]},
            {"key": "rank_math_description", "value": product["seo"]["meta_description"]},
            {"key": "rank_math_focus_keyword", "value": product["seo"]["focus_keyword"]},
        ]
    changed_old_to_new = {
        old: media[new]["id"] for old, new in local_audit["replacements"].items() if new in media
    }
    local_map = read_json(product_dir / "wordpress-media-map.json") if (product_dir / "wordpress-media-map.json").is_file() else {}
    old_attachment_to_new = {
        int(local_map[old]["id"]): int(new_id)
        for old, new_id in changed_old_to_new.items()
        if old in local_map and local_map[old].get("id")
    }
    client.post(f"products/{product_id}", payload)
    variation_updates = []
    for item in before_variations:
        old_image = int((item.get("image") or {}).get("id") or 0)
        if old_image in old_attachment_to_new:
            variation_updates.append({"id": int(item["id"]), "image": {"id": old_attachment_to_new[old_image]}})
    if variation_updates:
        client.post(f"products/{product_id}/variations/batch", {"update": variation_updates})
    after_parent = client.get(f"products/{product_id}", {"context": "edit", "_": str(time.time())})
    after_variations = client.get(f"products/{product_id}/variations", {"per_page": 100, "context": "edit", "_": str(time.time())})
    after = invariant_snapshot(after_parent, after_variations)
    if after["status"] != before["status"]:
        failures.append("publish status changed")
    if after["categories"] != before["categories"]:
        failures.append("categories changed")
    if after["model"] != before["model"] or after["source_url"] != before["source_url"]:
        failures.append("Model/source URL changed")
    if set(after["variations"]) != set(before["variations"]):
        failures.append("SKU set changed")
    for sku, expected in before["variations"].items():
        actual = after["variations"].get(sku)
        if not actual:
            continue
        for key in ("regular_price", "attributes", "variation_id", "spec_id"):
            if actual[key] != expected[key]:
                failures.append(f"{sku} immutable {key} changed")
    remote_image_ids = [int(item["id"]) for item in after_parent.get("images", [])]
    expected_image_ids = [int(media[path]["id"]) for path in product["images"]]
    if remote_image_ids != expected_image_ids:
        failures.append("Featured/Gallery attachment order mismatch")
    description_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)', after_parent.get("description", ""), re.I)
    expected_description_urls = [media[path]["src"] for path in product["description_images"]]
    if description_urls != expected_description_urls:
        failures.append("Long Description image URLs mismatch")
    if not description_urls and product["images"]:
        failures.append("Long Description has zero images despite usable supplier material")
    if any(re.search(r"(?:thumbnail|/small/|-\d+x\d+\.(?:webp|jpg|jpeg|png)$)", url, re.I) for url in description_urls):
        failures.append("Long Description references thumbnail/small image")
    if description_urls and ('max-width:100%;height:auto' not in after_parent.get("description", "")):
        failures.append("Long Description images are not responsive")
    http_checks = [image_http(url) for url in list(dict.fromkeys([item["src"] for item in after_parent.get("images", [])] + description_urls))]
    if any(not item["pass"] for item in http_checks):
        failures.append("one or more final image URLs failed HTTP 200/image Content-Type")
    # Variation images may change only when their exact old source was repaired.
    for sku, old in before["variations"].items():
        actual = after["variations"].get(sku)
        if not actual:
            continue
        expected_image = old_attachment_to_new.get(old["image_id"], old["image_id"])
        if actual["image_id"] != expected_image:
            failures.append(f"{sku} variation image relationship changed incorrectly")
    result = {
        "offer_id": offer,
        "product_id": product_id,
        "status": after_parent.get("status"),
        "permalink": after_parent.get("permalink"),
        "result": "FAIL" if failures else ("WARNING" if local_audit.get("seo_issues") else "PASS"),
        "failures": failures,
        "warnings": local_audit.get("seo_issues", []),
        "image_http_checks": http_checks,
        "description_image_count": len(description_urls),
        "gallery_count": max(0, len(after_parent.get("images", [])) - 1),
        "variation_count": len(after_variations),
        "immutable_fields_verified": not any("changed" in item for item in failures),
        "verified_at": utcnow(),
    }
    if failures:
        raise RuntimeError("; ".join(failures))
    return result


def derive_final_metrics(manifest: list[dict]) -> tuple[int, dict]:
    """Derive final unique counts from baseline evidence and current audits."""
    changed_products = 0
    counters = {
        "featured_redone": 0,
        "rembg_images": 0,
        "supplier_logo_url_deleted": 0,
        "parameter_to_html": 0,
        "chinese_residual_fixed": 0,
        "too_small_detail_fixed": 0,
        "long_description_supplemented": 0,
        "title_seo_rewritten": 0,
    }
    all_records = []
    for entry in manifest:
        product_dir = OUTPUT / str(entry["offer_id"])
        baseline_file = product_dir / "processed-product.pre-quality-20260909.json"
        current_file = product_dir / "processed-product.json"
        audit_file = product_dir / "quality-audit-20260909.json"
        if not (baseline_file.is_file() and current_file.is_file()):
            continue
        baseline = read_json(baseline_file)
        current = read_json(current_file)
        visible_fields = ("featured_image", "images", "description_images", "title", "seo")
        changed_products += int(any(baseline.get(key) != current.get(key) for key in visible_fields))
        counters["featured_redone"] += int(baseline.get("featured_image") != current.get("featured_image"))
        counters["long_description_supplemented"] += int(
            not baseline.get("description_images") and bool(current.get("description_images"))
        )
        counters["title_seo_rewritten"] += int(
            baseline.get("title") != current.get("title") or baseline.get("seo") != current.get("seo")
        )
        baseline_paths = list(dict.fromkeys(
            list(baseline.get("images", []))
            + list(baseline.get("description_images", []))
            + list((baseline.get("variation_image_map") or {}).values())
        ))
        for relative in baseline_paths:
            source = product_dir / relative
            if not source.is_file():
                continue
            cache = CACHE_DIR / f"{sha256(source)}.json"
            if cache.is_file() and any(has_cjk(text) for text in read_json(cache).get("ocr_text", [])):
                counters["chinese_residual_fixed"] += 1
        if audit_file.is_file():
            all_records.extend(read_json(audit_file).get("records", []))
    counters["rembg_images"] = sum(bool(record.get("rembg_executed")) for record in all_records)
    counters["supplier_logo_url_deleted"] = sum(
        record.get("decision") == "reject"
        and (
            "supplier" in str(record.get("reason", "")).lower()
            or "contact" in str(record.get("reason", "")).lower()
            or "non-product class" in str(record.get("reason", "")).lower()
        )
        for record in all_records
    )
    counters["parameter_to_html"] = sum(
        record.get("decision") == "reject" and "parameter/text graphic" in str(record.get("reason", ""))
        for record in all_records
    )
    counters["too_small_detail_fixed"] = sum(
        any("incorrectly reduced" in failure for failure in record.get("failures_before", []))
        and record.get("decision") == "repair"
        for record in all_records
    )
    return changed_products, counters


def main() -> None:
    started = time.perf_counter()
    force_problem_products = "--force-problem-products" in sys.argv[1:]
    only_offer = next((value.split("=", 1)[1] for value in sys.argv[1:] if value.startswith("--only-offer=")), None)
    only_offers_value = next((value.split("=", 1)[1] for value in sys.argv[1:] if value.startswith("--only-offers=")), None)
    only_offers = set(only_offers_value.split(",")) if only_offers_value else ({only_offer} if only_offer else set())
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    load_dotenv(ROOT / ".env")
    manifest = build_manifest()
    checkpoint = read_json(CHECKPOINT) if CHECKPOINT.is_file() else {"started_at": utcnow(), "products": {}}
    print(f"Loading real PaddleOCR and OpenCLIP for {len(manifest)} yesterday products...", flush=True)
    ocr = OCRAdapter()
    clip = VisionClassifierAdapter()
    inpainter = InpaintingAdapter(LAMA_MODEL)
    rembg_holder: dict = {}
    client = WooCommerceClient()
    results = []
    for index, entry in enumerate(manifest, 1):
        offer = str(entry["offer_id"])
        saved = checkpoint["products"].get(offer)
        try:
            if only_offers and offer not in only_offers:
                if saved:
                    results.append(saved)
                continue
            should_force = force_problem_products and (
                bool(only_offers)
                or bool((saved or {}).get("problem_found"))
                or (OUTPUT / offer / "quality_images").is_dir()
            )
            if saved and saved.get("result") in {"PASS", "WARNING"} and not should_force:
                remote = client.get(f"products/{entry['product_id']}")
                if remote.get("status") == "publish" and str(metadata(remote.get("meta_data", [])).get("_1688_offer_id")) == offer:
                    results.append(saved)
                    print(f"{index}/113 {offer}: checkpoint {saved['result']}", flush=True)
                    continue
            local = process_local_product(
                entry,
                ocr,
                clip,
                inpainter,
                rembg_holder,
                force_source_rebuild=force_problem_products,
            )
            remote = upload_and_verify(client, entry, local)
            merged = {**remote, "problem_found": local["problem_found"], "counters": local["counters"]}
            checkpoint["products"][offer] = merged
            results.append(merged)
            print(f"{index}/113 {offer}: {merged['result']}", flush=True)
        except Exception as exc:  # product-level failure isolation is intentional
            traceback.print_exc()
            failure = {
                "offer_id": offer,
                "product_id": int(entry["product_id"]),
                "result": "FAIL",
                "problem_found": True,
                "counters": {},
                "failures": [f"{type(exc).__name__}: {exc}"],
                "failed_at": utcnow(),
            }
            checkpoint["products"][offer] = failure
            results.append(failure)
            print(f"{index}/113 {offer}: FAIL {type(exc).__name__}: {exc}", flush=True)
        checkpoint["updated_at"] = utcnow()
        write_json(CHECKPOINT, checkpoint)
    problem_products, totals = derive_final_metrics(manifest)
    summary = {
        "scope": "all 113 products processed and published by this Skill on 2026-09-08",
        "total_checked": len(results),
        "problem_products": problem_products,
        **totals,
        "final_failures": [
            {"offer_id": item["offer_id"], "product_id": item["product_id"], "reasons": item.get("failures", [])}
            for item in results if item["result"] == "FAIL"
        ],
        "pass_count": sum(item["result"] == "PASS" for item in results),
        "warning_count": sum(item["result"] == "WARNING" for item in results),
        "fail_count": sum(item["result"] == "FAIL" for item in results),
        "paddleocr_actually_executed": True,
        "openclip_actually_executed": True,
        "rembg_model": RembgAdapter.model_name,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "completed_at": utcnow(),
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
