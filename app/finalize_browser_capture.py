"""Finalize a sanitized browser capture into the standard product JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .collector import download_images
from .core import calculate_sale_price


def parse_detail_payload(text: str) -> tuple[str, list[str]]:
    match = re.search(r"var\s+offer_details\s*=\s*({.*})\s*;?\s*$", text, re.S)
    if not match:
        raise ValueError("Unsupported 1688 detail payload")
    description = json.loads(match.group(1))["content"]
    soup = BeautifulSoup(description, "html.parser")
    images = [str(img["src"]) for img in soup.find_all("img", src=True)]
    return description, images


def finalize(capture_file: Path, detail_file: Path, output_file: Path) -> dict:
    capture = json.loads(capture_file.read_text(encoding="utf-8"))
    description, detail_images = parse_detail_payload(detail_file.read_text(encoding="utf-8"))
    image_urls = list(dict.fromkeys([*capture["main_images"], *detail_images]))

    skus = []
    for sku in capture["skus"]:
        sku["sale_price"] = str(calculate_sale_price(sku["source_price"]))
        skus.append(sku)

    raw_dir = output_file.parent / capture["offer_id"] / "raw_images"
    raw_images = download_images(image_urls, raw_dir)
    product = {
        "status": "success",
        "offer_id": capture["offer_id"],
        "model": f"Model: {capture['offer_id']}",
        "source_url": capture["source_url"],
        "title": capture["title"],
        "description": description,
        "attributes": capture["attributes"],
        "skus": skus,
        "images": image_urls,
        "raw_images": raw_images,
        "missing_fields": [],
        "woocommerce_uploaded": False,
    }
    output_file.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
    return product


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--detail", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = finalize(args.capture, args.detail, args.output)
    print(json.dumps({"skus": len(result["skus"]), "images": len(result["raw_images"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
