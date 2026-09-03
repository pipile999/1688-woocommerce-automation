"""Run the mandatory PaddleOCR + OpenCLIP + LaMa product-image pipeline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .image_pipeline import (
    DELETE_CLASSES,
    InpaintingAdapter,
    OCRAdapter,
    VisionClassifierAdapter,
    optimize_webp,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate(raw_dir: Path) -> list[dict]:
    groups: dict[str, list[Path]] = {}
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            groups.setdefault(file_sha256(path), []).append(path)
    return [
        {
            "sha256": digest,
            "path": paths[0],
            "duplicates": [path.name for path in paths[1:]],
        }
        for digest, paths in groups.items()
    ]


def is_peripheral_text(detections: list, width: int, height: int) -> bool:
    if not detections:
        return False
    for detection in detections:
        xs = [point[0] for point in detection.polygon]
        ys = [point[1] for point in detection.polygon]
        center_x = (min(xs) + max(xs)) / 2
        center_y = (min(ys) + max(ys)) / 2
        if 0.18 * width < center_x < 0.82 * width and 0.18 * height < center_y < 0.82 * height:
            return False
    return True


def decide_from_model_outputs(classification, ocr, width: int, height: int) -> tuple[bool, str, bool]:
    recognized_text = " ".join(item.text for item in ocr.detections).upper()
    infographic_markers = (
        "PRODUCT ANALYSIS",
        "PRODUCT PARAMETERS",
        "SHOW DETAILS",
        "DIFFERENT TOOTH",
        "SHOP RECOMMENDATION",
    )
    matched_marker = next(
        (marker for marker in infographic_markers if marker in recognized_text), None
    )
    if matched_marker:
        return False, f"PaddleOCR identified infographic marker: {matched_marker}", False
    if classification.label in DELETE_CLASSES:
        return False, f"OpenCLIP blocked class: {classification.label}", False
    if ocr.text_coverage >= 0.12:
        return False, "PaddleOCR text coverage is at least 12%", False
    if ocr.detections and not is_peripheral_text(ocr.detections, width, height):
        return False, "PaddleOCR detected text in the central product area", False
    if ocr.detections:
        return True, "small peripheral text/watermark; LaMa inpainting required", True
    return True, "clean product photo; no OCR text detected", False


def replace_directory(staging: Path, destination: Path) -> None:
    staging = staging.resolve()
    destination = destination.resolve()
    if staging.parent != destination.parent:
        raise ValueError("Refusing directory replacement across different parents")
    if destination.exists():
        shutil.rmtree(destination)
    staging.rename(destination)


def package_version(name: str) -> str:
    return importlib.metadata.version(name)


def run(product_dir: Path, lama_model: Path) -> dict:
    product_dir = product_dir.resolve()
    raw_dir = product_dir / "raw_images"
    if not raw_dir.is_dir():
        raise FileNotFoundError(raw_dir)

    unique_images = deduplicate(raw_dir)
    if len(unique_images) != 25:
        raise AssertionError(f"Expected 25 SHA-unique images, found {len(unique_images)}")

    print("Loading PaddleOCR...", flush=True)
    ocr_engine = OCRAdapter()
    print("Loading OpenCLIP...", flush=True)
    classifier = VisionClassifierAdapter()
    print("Loading LaMa ONNX...", flush=True)
    inpainter = InpaintingAdapter(lama_model.resolve())

    staging_images = product_dir / "processed_images_ai_staging"
    staging_masks = product_dir / "image_audit" / "ai_masks_staging"
    for directory in (staging_images, staging_masks):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    records = []
    for index, item in enumerate(unique_images, start=1):
        path = item["path"]
        image_bytes = path.read_bytes()
        with Image.open(path) as image:
            width, height = image.size
        print(f"[{index:02d}/25] OCR + OpenCLIP: {path.name}", flush=True)
        ocr = ocr_engine.analyze(image_bytes)
        classification = classifier.classify(image_bytes)
        keep, reason, needs_inpainting = decide_from_model_outputs(
            classification, ocr, width, height
        )

        mask_file = None
        output_file = None
        inpainting_executed = False
        final_bytes = image_bytes
        if keep and needs_inpainting:
            mask_path = staging_masks / f"{path.stem}-mask.png"
            ocr.mask.save(mask_path)
            mask_file = f"image_audit/ai_masks/{mask_path.name}"
            print(f"[{index:02d}/25] LaMa inpainting: {path.name}", flush=True)
            final_bytes = inpainter.inpaint(image_bytes, ocr.mask)
            inpainting_executed = True
        if keep:
            output_path = staging_images / f"{path.stem}.webp"
            output_path.write_bytes(optimize_webp(final_bytes, max_edge=1800, quality=83))
            output_file = f"processed_images/{output_path.name}"

        records.append(
            {
                "filename": path.name,
                "sha256": item["sha256"],
                "duplicate_filenames": item["duplicates"],
                "width": width,
                "height": height,
                "ocr_text": [entry.text for entry in ocr.detections],
                "text_coverage": round(ocr.text_coverage, 6),
                "ocr_detections": ocr.json_data()["detections"],
                "classification": {
                    "label": classification.label,
                    "confidence": round(classification.confidence, 6),
                    "scores": classification.scores,
                },
                "keep": keep,
                "delete": not keep,
                "delete_reason": None if keep else reason,
                "decision_reason": reason,
                "needs_inpainting": needs_inpainting,
                "inpainting_executed": inpainting_executed,
                "mask_file": mask_file,
                "output_file": output_file,
            }
        )

    processed_dir = product_dir / "processed_images"
    masks_dir = product_dir / "image_audit" / "ai_masks"
    replace_directory(staging_images, processed_dir)
    replace_directory(staging_masks, masks_dir)

    kept = sum(record["keep"] for record in records)
    inpainted = sum(record["inpainting_executed"] for record in records)
    audit = {
        "offer_id": "582636594501",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution": {
            "paddleocr": {
                "executed": True,
                "paddleocr_version": package_version("paddleocr"),
                "paddlepaddle_version": package_version("paddlepaddle"),
                "detection_model": OCRAdapter.detection_model,
                "recognition_model": OCRAdapter.recognition_model,
                "device": "cpu",
            },
            "openclip": {
                "executed": True,
                "open_clip_torch_version": package_version("open-clip-torch"),
                "torch_version": package_version("torch"),
                "model": VisionClassifierAdapter.model_name,
                "pretrained": VisionClassifierAdapter.pretrained,
                "device": "cpu",
            },
            "inpainting": {
                "executed": inpainted > 0,
                "engine": "LaMa FP32 ONNX",
                "model": InpaintingAdapter.model_name,
                "onnxruntime_version": package_version("onnxruntime"),
                "device": "cpu",
            },
        },
        "summary": {
            "source_count": 31,
            "sha_unique_count": len(records),
            "sha_duplicate_count": 31 - len(records),
            "deleted_count": len(records) - kept,
            "inpainted_count": inpainted,
            "final_kept_count": kept,
        },
        "records": records,
    }
    audit_path = product_dir / "image-audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    processed_json = product_dir / "processed-product.json"
    product = json.loads(processed_json.read_text(encoding="utf-8"))
    product["images"] = [record["output_file"] for record in records if record["keep"]]
    product["processing"] = {
        **audit["summary"],
        "format": "WebP",
        "longest_edge_px": 1800,
        "quality": 83,
        "exif_removed": True,
        "audit_file": "image-audit.json",
        "model_execution": audit["execution"],
    }
    processed_json.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", required=True, type=Path)
    parser.add_argument("--lama-model", required=True, type=Path)
    args = parser.parse_args()
    audit = run(args.product_dir, args.lama_model)
    print(json.dumps(audit["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
