"""Export a collected product as a WooCommerce product-import CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


HEADERS = [
    "Type", "SKU", "Name", "Published", "Is featured?", "Visibility in catalog",
    "Short description", "Description", "Tax status", "In stock?", "Stock",
    "Regular price", "Parent", "Images",
    "Attribute 1 name", "Attribute 1 value(s)", "Attribute 1 visible", "Attribute 1 global",
    "Attribute 2 name", "Attribute 2 value(s)", "Attribute 2 visible", "Attribute 2 global",
    "Meta: _1688_offer_id", "Meta: _1688_source_url",
    "Meta: _1688_source_variant_id", "Meta: _1688_spec_id", "Meta: _1688_source_price",
]


def export_csv(source: Path, destination: Path) -> int:
    product = json.loads(source.read_text(encoding="utf-8"))
    parent_sku = f"1688-{product['offer_id']}"
    colors = list(dict.fromkeys(v["attributes"]["颜色"] for v in product["skus"]))
    sizes = list(dict.fromkeys(v["attributes"]["规格"] for v in product["skus"]))
    description = product["description"] + (
        f'<p><strong>Model:</strong> {product["offer_id"]}</p>'
        f'<p><strong>Source:</strong> <a href="{product["source_url"]}">{product["source_url"]}</a></p>'
    )
    rows = [{
        "Type": "variable",
        "SKU": parent_sku,
        "Name": product["title"],
        "Published": -1,
        "Is featured?": 0,
        "Visibility in catalog": "visible",
        "Description": description,
        "Tax status": "taxable",
        "In stock?": 1,
        "Images": ", ".join(product["images"]),
        "Attribute 1 name": "颜色",
        "Attribute 1 value(s)": ", ".join(colors),
        "Attribute 1 visible": 1,
        "Attribute 1 global": 0,
        "Attribute 2 name": "规格",
        "Attribute 2 value(s)": ", ".join(sizes),
        "Attribute 2 visible": 1,
        "Attribute 2 global": 0,
        "Meta: _1688_offer_id": product["offer_id"],
        "Meta: _1688_source_url": product["source_url"],
    }]
    for variation in product["skus"]:
        color = variation["attributes"]["颜色"]
        size = variation["attributes"]["规格"]
        rows.append({
            "Type": "variation",
            "SKU": variation["sku"],
            "Name": f'{product["title"]} - {color} - {size}',
            "Published": 1,
            "Tax status": "taxable",
            "In stock?": 1,
            "Stock": variation["stock"],
            "Regular price": variation["sale_price"],
            "Parent": parent_sku,
            "Attribute 1 name": "颜色",
            "Attribute 1 value(s)": color,
            "Attribute 1 visible": 1,
            "Attribute 1 global": 0,
            "Attribute 2 name": "规格",
            "Attribute 2 value(s)": size,
            "Attribute 2 visible": 1,
            "Attribute 2 global": 0,
            "Meta: _1688_offer_id": product["offer_id"],
            "Meta: _1688_source_url": product["source_url"],
            "Meta: _1688_source_variant_id": variation["variation_id"],
            "Meta: _1688_spec_id": variation["spec_id"],
            "Meta: _1688_source_price": variation["source_price"],
        })

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(export_csv(args.source, args.output))


if __name__ == "__main__":
    main()
