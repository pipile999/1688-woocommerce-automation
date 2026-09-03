"""Prepare a captured 1688 product for a clean English storefront listing."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


ENGLISH_TITLE = "4-Layer Zinc Alloy Grinder with Storage Chamber, 40-75 mm"

ATTRIBUTE_NAMES = {
    "附加功能": "Features",
    "防风功能": "Windproof Function",
    "风格": "Style",
    "是否一次性": "Disposable",
    "是否进口": "Imported",
    "货号": "Item Number",
    "箱装数量": "Carton Quantity",
    "是否专利货源": "Patented Product",
    "颜色": "Color",
    "规格": "Size",
}

ATTRIBUTE_VALUES = {
    "装饰": "Decorative",
    "收藏": "Collectible",
    "收纳": "Storage",
    "有": "Yes",
    "无": "No",
    "是": "Yes",
    "否": "No",
    "简约": "Minimalist",
    "黑": "Black",
    "枪": "Gunmetal",
    "银": "Silver",
    "红": "Red",
    "蓝": "Blue",
    "绿": "Green",
    "炫彩": "Rainbow",
    "金色": "Gold",
    "包花随机图": "Random Floral Pattern",
    "玫瑰金": "Rose Gold",
    "40mm（四层）": "40 mm (4-Layer)",
    "50mm（四层）": "50 mm (4-Layer)",
    "55mm（四层）": "55 mm (4-Layer)",
    "63mm（四层）": "63 mm (4-Layer)",
    "75mm（四层）": "75 mm (4-Layer)",
}

KEEP_IMAGES = [
    "002.jpg",
    "003.jpg",
    "004.jpg",
    "005.jpg",
    "006.jpg",
    "007.jpg",
    "008.jpg",
    "009.jpg",
    "010.jpg",
    "011.jpg",
    "012.jpg",
    "013.jpg",
    "015.jpg",
]

INPAINT_IMAGES = [
    "002.jpg",
    "003.jpg",
    "005.jpg",
    "006.jpg",
    "007.jpg",
    "008.jpg",
    "009.jpg",
    "010.jpg",
    "011.jpg",
    "012.jpg",
]

DELETE_IMAGES = {
    "001.jpg": "supplier logo and large marketing text",
    "014.jpg": "company promotion, contact handle, and large text",
    "016.jpg": "store recommendations and advertising",
    "017.jpg": "large promotional and specification text",
    "018.jpg": "large specification text",
    "019.jpg": "large specification text",
    "020.jpg": "large specification text",
    "021.jpg": "large product-analysis text",
    "028.jpg": "large tooth-comparison text",
    "029.jpg": "large annotation text",
    "030.jpg": "large annotation text",
    "031.jpg": "large annotation text",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_images(raw_dir: Path, audit_dir: Path) -> dict:
    """Hash-deduplicate source images and render numbered contact sheets."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[Path]] = {}
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            groups.setdefault(sha256(path), []).append(path)

    entries = []
    for index, (digest, paths) in enumerate(groups.items(), start=1):
        with Image.open(paths[0]) as image:
            width, height = image.size
        entries.append(
            {
                "number": index,
                "canonical": paths[0].name,
                "duplicates": [path.name for path in paths[1:]],
                "sha256": digest,
                "width": width,
                "height": height,
            }
        )

    page_size = 12
    cell_width, cell_height = 360, 390
    for page, start in enumerate(range(0, len(entries), page_size), start=1):
        subset = entries[start : start + page_size]
        sheet = Image.new("RGB", (cell_width * 4, cell_height * 3), "white")
        draw = ImageDraw.Draw(sheet)
        for slot, entry in enumerate(subset):
            x = (slot % 4) * cell_width
            y = (slot // 4) * cell_height
            with Image.open(raw_dir / entry["canonical"]) as source:
                preview = ImageOps.contain(source.convert("RGB"), (340, 340))
            px = x + (cell_width - preview.width) // 2
            py = y + 26 + (340 - preview.height) // 2
            sheet.paste(preview, (px, py))
            duplicate_note = (
                f" duplicates: {','.join(entry['duplicates'])}" if entry["duplicates"] else ""
            )
            draw.text((x + 8, y + 7), f"#{entry['number']:02d} {entry['canonical']}{duplicate_note}", fill="black")
        sheet.save(audit_dir / f"contact-sheet-{page}.jpg", quality=90)

    report = {
        "source_count": sum(len(paths) for paths in groups.values()),
        "unique_count": len(groups),
        "duplicate_count": sum(len(paths) - 1 for paths in groups.values()),
        "entries": entries,
    }
    (audit_dir / "sha-deduplication.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def backup_json(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)


def watermark_mask(image: Image.Image) -> Image.Image:
    """Build a conservative mask for the pale supplier watermark on white."""
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    low = rgb.min(axis=2)
    high = rgb.max(axis=2)
    neutral = (high - low) <= 18
    pale_ink = (low >= 175) & (high <= 253)
    region = np.zeros((height, width), dtype=bool)
    region[int(height * 0.84) :, int(width * 0.42) :] = True
    mask = Image.fromarray(np.where(neutral & pale_ink & region, 255, 0).astype("uint8"))
    return mask.filter(ImageFilter.MaxFilter(7))


def inpaint_flat_background(image: Image.Image, mask: Image.Image) -> Image.Image:
    """Inpaint masked peripheral pixels from the surrounding white backdrop."""
    source = image.convert("RGB")
    border = np.asarray(source)
    sample = np.concatenate(
        [border[:20].reshape(-1, 3), border[-20:].reshape(-1, 3), border[:, :20].reshape(-1, 3)]
    )
    light = sample[sample.mean(axis=1) > 235]
    fill = tuple(int(value) for value in np.median(light, axis=0)) if len(light) else (255, 255, 255)
    background = Image.new("RGB", source.size, fill)
    feathered = mask.filter(ImageFilter.GaussianBlur(1.2))
    return Image.composite(background, source, feathered)


def save_webp(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = image.size
    scale = 1800 / max(width, height)
    resized = image.resize(
        (round(width * scale), round(height * scale)), Image.Resampling.LANCZOS
    )
    resized.save(destination, "WEBP", quality=83, method=6, exif=b"")


def translate_attributes(attributes: dict) -> dict:
    translated: dict[str, list[dict]] = {}
    for group_name, entries in attributes.items():
        clean_entries = []
        for entry in entries:
            english_name = ATTRIBUTE_NAMES.get(entry["name"])
            if not english_name:
                continue
            clean_entries.append(
                {
                    "name": english_name,
                    "values": [ATTRIBUTE_VALUES.get(value, value) for value in entry["values"]],
                }
            )
        translated[group_name] = clean_entries
    return translated


def translate_skus(skus: list[dict]) -> list[dict]:
    result = deepcopy(skus)
    for sku in result:
        sku["attributes"] = {
            ATTRIBUTE_NAMES.get(name, name): ATTRIBUTE_VALUES.get(value, value)
            for name, value in sku["attributes"].items()
        }
    return result


def neutral_description() -> str:
    return (
        "<p>This four-layer manual grinder is made from zinc alloy and includes "
        "a grinding section, collection chamber, fine screen, and lower storage chamber.</p>"
        "<ul>"
        "<li>Material: zinc alloy</li>"
        "<li>Available diameters: 40, 50, 55, 63, and 75 mm</li>"
        "<li>Colors: black, gunmetal, silver, red, blue, green, rainbow, gold, "
        "random floral pattern, and rose gold</li>"
        "<li>Construction: four-layer threaded body with textured grip edges</li>"
        "<li>Functions: grinding, collection, and storage</li>"
        "<li>Carton quantity: 100 units; individual package dimensions and weights "
        "vary by SKU and are recorded in the variant data</li>"
        "</ul><p>Model: 582636594501</p>"
    )


def build_processed_product(source_file: Path, product_dir: Path, report: dict) -> dict:
    product = json.loads(source_file.read_text(encoding="utf-8"))
    raw_dir = product_dir / "raw_images"
    mask_dir = product_dir / "image_audit" / "masks"
    processed_dir = product_dir / "processed_images"
    mask_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    for old_file in processed_dir.glob("*.webp"):
        old_file.unlink()
    for old_file in mask_dir.glob("*.png"):
        old_file.unlink()

    processed_paths = []
    for filename in KEEP_IMAGES:
        with Image.open(raw_dir / filename) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        if filename in INPAINT_IMAGES:
            mask = watermark_mask(image)
            mask.save(mask_dir / f"{Path(filename).stem}-mask.png")
            image = inpaint_flat_background(image, mask)
        destination = processed_dir / f"{Path(filename).stem}.webp"
        save_webp(image, destination)
        processed_paths.append(f"processed_images/{destination.name}")

    original_skus = product["skus"]
    translated_skus = translate_skus(original_skus)
    for before, after in zip(original_skus, translated_skus, strict=True):
        for protected in ("sku", "variation_id", "spec_id", "source_price", "sale_price"):
            if before[protected] != after[protected]:
                raise AssertionError(f"Protected SKU field changed: {protected}")

    result = deepcopy(product)
    result["title"] = ENGLISH_TITLE
    result["description"] = neutral_description()
    result["attributes"] = translate_attributes(product["attributes"])
    result["skus"] = translated_skus
    result["original_image_urls"] = product["images"]
    result["images"] = processed_paths
    result["processing"] = {
        "source_image_count": report["source_count"],
        "sha_unique_count": report["unique_count"],
        "sha_duplicate_count": report["duplicate_count"],
        "deleted_count": len(DELETE_IMAGES),
        "deleted_images": DELETE_IMAGES,
        "inpainted_count": len(INPAINT_IMAGES),
        "inpainted_images": INPAINT_IMAGES,
        "final_image_count": len(processed_paths),
        "format": "WebP",
        "longest_edge_px": 1800,
        "quality": 83,
        "exif_removed": True,
    }
    result["woocommerce_uploaded"] = False
    (product_dir / "processed-product.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--product-dir", required=True, type=Path)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    args.product_dir.mkdir(parents=True, exist_ok=True)
    backup_json(args.source, args.product_dir / "original-product.json")
    report = audit_images(args.product_dir / "raw_images", args.product_dir / "image_audit")
    if args.audit_only:
        print(json.dumps(report, ensure_ascii=False))
        return
    result = build_processed_product(args.source, args.product_dir, report)
    print(
        json.dumps(
            {
                "title": result["title"],
                "skus": len(result["skus"]),
                **result["processing"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
