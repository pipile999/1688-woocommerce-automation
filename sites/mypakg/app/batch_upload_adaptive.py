"""Upload the five audited products as WooCommerce drafts and verify them.

The script is deliberately idempotent: it reuses media recorded locally and
resumes a matching draft instead of creating duplicate products.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from decimal import Decimal
from pathlib import Path

import requests
from dotenv import load_dotenv

from .woocommerce import WooCommerceClient


ROOT = Path(__file__).resolve().parents[1]
OFFERS = ()  # Historical batch entry disabled.
CATEGORY_FIXES = {}  # No inherited product/category IDs.


def metadata(items: list[dict]) -> dict:
    return {str(item.get("key")): item.get("value") for item in items}


def ordered_unique(values) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def wp_auth() -> tuple[str, str]:
    return os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APPLICATION_PASSWORD"]


def wp_request(client: WooCommerceClient, method: str, path: str, **kwargs) -> requests.Response:
    from .site_guard import endpoint
    endpoint(client.base_url, "wp", method, path)
    response = requests.request(
        method,
        f"{client.base_url}/wp-json/wp/v2/{path.lstrip('/')}",
        auth=wp_auth(),
        allow_redirects=False,
        timeout=kwargs.pop("timeout", 120),
        **kwargs,
    )
    if 300 <= response.status_code < 400:
        raise ValueError("HARD STOP: STORE_REDIRECT")
    response.raise_for_status()
    return response


def verify_public_image(url: str) -> dict:
    response = requests.get(url, stream=True, timeout=60)
    result = {
        "url": url,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", "").split(";", 1)[0].lower(),
    }
    response.close()
    result["pass"] = result["http_status"] == 200 and result["content_type"].startswith("image/")
    return result


def media_alt(product: dict, relative: str) -> str:
    stem = Path(relative).stem.replace("-", " ")
    return stem[:1].upper() + stem[1:]


def upload_media(client: WooCommerceClient, product_dir: Path, product: dict) -> dict[str, dict]:
    media_file = product_dir / "wordpress-media-map.json"
    saved = json.loads(media_file.read_text(encoding="utf-8")) if media_file.exists() else {}
    required = ordered_unique(product["images"] + product.get("description_images", []))
    result: dict[str, dict] = {}
    for relative in required:
        path = product_dir / relative
        if path.suffix.lower() != ".webp" or not path.is_file():
            raise RuntimeError(f"Final WebP missing or invalid: {path}")
        previous = saved.get(relative)
        if previous:
            try:
                item = wp_request(client, "GET", f"media/{int(previous['id'])}", timeout=30).json()
                if item.get("source_url"):
                    result[relative] = {"id": int(item["id"]), "src": item["source_url"]}
                    continue
            except requests.RequestException:
                pass
        alt = media_alt(product, relative)
        with path.open("rb") as stream:
            response = wp_request(
                client,
                "POST",
                "media",
                files={"file": (f"{product['offer_id']}-{path.name}", stream, "image/webp")},
                data={"title": alt, "alt_text": alt, "caption": ""},
                timeout=180,
            )
        item = response.json()
        result[relative] = {"id": int(item["id"]), "src": item["source_url"]}
        saved[relative] = result[relative]
        media_file.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_description(product: dict, media: dict[str, dict]) -> str:
    chunks = ["<h2>Product Overview</h2>", f"<p>{html.escape(product['description_overview'])}</p>"]
    bullets = product.get("description_bullets", [])
    if bullets:
        chunks.extend(("<h2>Product Details</h2>", "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in bullets) + "</ul>"))
    for relative in product.get("description_images", []):
        item = media[relative]
        alt = html.escape(media_alt(product, relative), quote=True)
        chunks.append(f'<figure class="wp-block-image size-large"><img src="{html.escape(item["src"], quote=True)}" alt="{alt}" loading="lazy"></figure>')
    specs = product.get("description_specs", {})
    if specs:
        rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in specs.items())
        chunks.extend(("<h2>Specifications</h2>", f"<table><tbody>{rows}</tbody></table>"))
    chunks.append(f"<p><strong>Model:</strong> {product['offer_id']}</p>")
    return "\n".join(chunks)


def build_attributes(product: dict) -> list[dict]:
    variation_names = ordered_unique(name for sku in product["skus"] for name in sku["attributes"])
    attributes = [
        {
            "name": name,
            "visible": True,
            "variation": True,
            "options": ordered_unique(sku["attributes"][name] for sku in product["skus"] if name in sku["attributes"]),
        }
        for name in variation_names
    ]
    attributes.append({"name": "Model", "visible": True, "variation": False, "options": [str(product["offer_id"])]})
    used = set(variation_names) | {"Model"}
    for item in product.get("attributes", {}).get("normalCpv", []):
        if item["name"] not in used and item.get("values"):
            attributes.append({"name": item["name"], "visible": True, "variation": False, "options": ordered_unique(item["values"])})
            used.add(item["name"])
    return attributes


def variation_image(product: dict, sku: dict) -> tuple[str, str, str]:
    offer = str(product["offer_id"])
    attrs = sku["attributes"]
    if offer == "694850755461":
        color = attrs.get("Color")
        if color == "Black":
            return "processed_images/black-long-spout-plastic-funnel.webp", "exact", "supplier provides a black variant image"
        if color == "Assorted Colors":
            return product["featured_image"], "exact", "supplier provides an assorted-color image"
        return "processed_images/plastic-funnel-color-options.webp", "fallback", "no reliable individual supplier image for this color"
    if offer == "621644442174":
        mapping = {
            "Black": "processed_images/black-aluminum-storage-tin.webp",
            "Green": "processed_images/green-aluminum-storage-tin.webp",
            "Blue": "processed_images/blue-aluminum-storage-tin.webp",
            "Silver": "processed_images/silver-aluminum-storage-tin.webp",
            "Gold": "processed_images/gold-aluminum-storage-tin.webp",
        }
        color = attrs.get("Color")
        if color in mapping:
            return mapping[color], "exact", "supplier provides an individual color image"
        return "processed_images/aluminum-storage-tin-color-selection.webp", "fallback", "no reliable individual supplier image for this color"
    return product["featured_image"], "exact", "single listed style uses the verified featured product image"


def build_parent_payload(product: dict, media: dict[str, dict]) -> dict:
    description = build_description(product, media)
    seo = product["seo"]
    return {
        "name": product["title"],
        "slug": product["slug"],
        "type": "variable",
        "status": "draft",
        "description": description,
        "short_description": f"<p>{html.escape(product['short_description'])}</p>",
        "categories": [{"id": int(product["category"]["id"])}],
        "images": [
            {"id": media[relative]["id"], "position": index, "name": media_alt(product, relative), "alt": media_alt(product, relative)}
            for index, relative in enumerate(product["images"])
        ],
        "attributes": build_attributes(product),
        "meta_data": [
            {"key": "_1688_offer_id", "value": str(product["offer_id"])},
            {"key": "_1688_model", "value": product["model"]},
            {"key": "_1688_source_url", "value": product["source_url"]},
            {"key": "rank_math_title", "value": seo["meta_title"]},
            {"key": "rank_math_description", "value": seo["meta_description"]},
            {"key": "rank_math_focus_keyword", "value": seo["focus_keyword"]},
        ],
    }


def build_variation_payload(product: dict, sku: dict, media: dict[str, dict]) -> tuple[dict, dict]:
    relative, binding, reason = variation_image(product, sku)
    price = str(sku["sale_price"])
    payload = {
        "sku": str(sku["sku"]),
        "regular_price": price,
        "manage_stock": True,
        "stock_quantity": int(sku.get("stock") or 0),
        "attributes": [{"name": name, "option": value} for name, value in sku["attributes"].items()],
        "image": {"id": media[relative]["id"]},
        "meta_data": [
            {"key": "_1688_variation_id", "value": str(sku["variation_id"])},
            {"key": "_1688_spec_id", "value": str(sku["spec_id"])},
            {"key": "_1688_source_spec_id", "value": str(sku.get("source_spec_id", sku["spec_id"]))},
            {"key": "_1688_source_price", "value": str(sku["source_price"])},
            {"key": "_1688_sale_price", "value": price},
        ],
    }
    audit = {"sku": str(sku["sku"]), "source_variation_id": str(sku["variation_id"]), "source_spec_id": str(sku["spec_id"]), "image": relative, "attachment_id": media[relative]["id"], "binding": binding, "reason": reason}
    return payload, audit


def find_product(client: WooCommerceClient, offer_id: str) -> dict | None:
    for item in client.get("products", {"search": offer_id, "status": "any", "per_page": 100}):
        if str(metadata(item.get("meta_data", [])).get("_1688_offer_id", "")) == offer_id:
            return item
    return None


def create_or_resume(client: WooCommerceClient, product_dir: Path, product: dict, media: dict[str, dict]) -> tuple[dict, list[dict], list[dict]]:
    offer = str(product["offer_id"])
    parent_payload = build_parent_payload(product, media)
    existing = find_product(client, offer)
    if existing:
        if existing.get("status") != "draft":
            raise RuntimeError(f"Refusing to update non-draft product {existing['id']} for offer {offer}")
        # This store's REST stack accepts POST updates but silently restores
        # some fields after PUT, so use WooCommerce's supported POST form.
        parent = client.post(f"products/{existing['id']}", parent_payload)
    else:
        parent = client.post("products", parent_payload)
    product_id = int(parent["id"])
    current = client.get(f"products/{product_id}/variations", {"per_page": 100})
    by_sku = {str(item["sku"]): item for item in current}
    create, update, audits = [], [], []
    for sku in product["skus"]:
        payload, audit = build_variation_payload(product, sku, media)
        if str(sku["sku"]) in by_sku:
            payload["id"] = int(by_sku[str(sku["sku"])]["id"])
            update.append(payload)
        else:
            create.append(payload)
        audits.append(audit)
    batch_payload = {}
    if create:
        batch_payload["create"] = create
    if update:
        batch_payload["update"] = update
    if batch_payload:
        batch = client.post(f"products/{product_id}/variations/batch", batch_payload)
        failures = [item for key in ("create", "update") for item in batch.get(key, []) if item.get("error") or not item.get("id")]
        if failures:
            raise RuntimeError(f"Variation batch returned {len(failures)} failures for {offer}")
    return client.get(f"products/{product_id}"), client.get(f"products/{product_id}/variations", {"per_page": 100}), audits


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def verify_product(client: WooCommerceClient, product_dir: Path, source: dict, parent: dict, variations: list[dict], binding_audit: list[dict]) -> dict:
    offer = str(source["offer_id"])
    failures, warnings = [], []
    meta = metadata(parent.get("meta_data", []))
    if parent.get("status") != "draft": failures.append("product is not Draft")
    if parent.get("type") != "variable": failures.append("product is not variable")
    if meta.get("_1688_model") != source["model"]: failures.append("Model metadata mismatch")
    if meta.get("_1688_source_url") != source["source_url"]: failures.append("source URL metadata mismatch")
    if f"Model:</strong> {offer}" not in parent.get("description", ""): failures.append("visible Model missing")
    category_ids = {int(item["id"]) for item in parent.get("categories", [])}
    if int(source["category"]["id"]) not in category_ids: failures.append("category mismatch")
    expected_images = [Path(item).name for item in source["images"]]
    actual_images = [Path(item.get("src", "")).name for item in parent.get("images", [])]
    if len(actual_images) != len(expected_images): failures.append("gallery image count mismatch")
    public_checks = [verify_public_image(item["src"]) for item in parent.get("images", [])]
    desc_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)', parent.get("description", ""), re.I)
    desc_checks = [verify_public_image(url) for url in desc_urls]
    if len(desc_urls) != len(source.get("description_images", [])): failures.append("description image count mismatch")
    if not all(item["pass"] for item in public_checks + desc_checks): failures.append("one or more final image URLs failed HTTP 200 image validation")
    expected_by_sku = {str(item["sku"]): item for item in source["skus"]}
    actual_by_sku = {str(item["sku"]): item for item in variations}
    if set(actual_by_sku) != set(expected_by_sku): failures.append("SKU set mismatch")
    binding_by_sku = {item["sku"]: item for item in binding_audit}
    for sku, expected in expected_by_sku.items():
        actual = actual_by_sku.get(sku)
        if not actual: continue
        if money(actual.get("regular_price", "0")) != money(expected["sale_price"]): failures.append(f"price mismatch for SKU {sku}")
        if {x["name"]: x["option"] for x in actual.get("attributes", [])} != expected["attributes"]: failures.append(f"attribute mismatch for SKU {sku}")
        vm = metadata(actual.get("meta_data", []))
        if str(vm.get("_1688_variation_id")) != str(expected["variation_id"]): failures.append(f"variation ID mismatch for SKU {sku}")
        if str(vm.get("_1688_spec_id")) != str(expected["spec_id"]): failures.append(f"spec ID mismatch for SKU {sku}")
        if int(actual.get("image", {}).get("id") or 0) != int(binding_by_sku[sku]["attachment_id"]): failures.append(f"variation image mismatch for SKU {sku}")
    fallback = [item for item in binding_audit if item["binding"] == "fallback"]
    if fallback: warnings.append(f"{len(fallback)} variations use a truthful group image because no exact supplier color image exists")
    # Confirm WordPress rendered content and featured media through a second REST surface.
    wp_product = wp_request(client, "GET", f"product/{parent['id']}", params={"context": "edit", "_": str(time.time())}, timeout=60).json()
    if int(wp_product.get("featured_media") or 0) != int(parent["images"][0]["id"]): failures.append("featured media mismatch in WordPress REST")
    rendered_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)', wp_product.get("content", {}).get("rendered", ""), re.I)
    rendered_checks = [verify_public_image(url) for url in rendered_urls]
    if len(rendered_urls) != len(source.get("description_images", [])): failures.append("rendered description image count mismatch")
    if not all(item["pass"] for item in rendered_checks): failures.append("rendered description contains a broken image")
    result = {
        "offer_id": offer,
        "product_id": int(parent["id"]),
        "status": parent["status"],
        "preview_url": f"{client.base_url}/?post_type=product&p={parent['id']}&preview=true",
        "category": source["category"],
        "sku_count": len(variations),
        "featured": parent["images"][0],
        "gallery_count": max(0, len(parent.get("images", [])) - 1),
        "description_image_count": len(desc_urls),
        "variation_result": "FAIL" if failures else ("WARNING" if fallback else "PASS"),
        "translation_pending": source.get("translation_pending", []),
        "warnings": warnings,
        "failures": failures,
        "variation_images": binding_audit,
        "image_http_checks": {"gallery": public_checks, "description": desc_checks, "rendered_description": rendered_checks},
    }
    (product_dir / "variation-image-audit.json").write_text(json.dumps({"offer_id": offer, "result": result["variation_result"], "records": binding_audit}, ensure_ascii=False, indent=2), encoding="utf-8")
    (product_dir / "final-product-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures:
        raise RuntimeError(f"Final acceptance failed for {offer}: {failures}")
    return result


def correct_existing_categories(client: WooCommerceClient) -> list[dict]:
    results = []
    for product_id, (offer, category_id, category_name) in CATEGORY_FIXES.items():
        before = client.get(f"products/{product_id}")
        meta_text = json.dumps(before.get("meta_data", []), ensure_ascii=False)
        if offer not in meta_text:
            raise RuntimeError(f"Refusing category change: product {product_id} is not Model {offer}")
        immutable = {"name": before["name"], "slug": before["slug"], "status": before["status"]}
        # A site hook restores the former category when this particular field is
        # written through wc/v3.  Update only the product_cat taxonomy through
        # authenticated WordPress REST, then verify through WooCommerce REST.
        wp_request(client, "POST", f"product/{product_id}", json={"product_cat": [category_id]})
        after = None
        for attempt in range(5):
            after = client.get(f"products/{product_id}", {"_": f"{time.time()}-{attempt}"})
            if [int(item["id"]) for item in after.get("categories", [])] == [category_id]:
                break
            time.sleep(1)
        assert after is not None
        if {"name": after["name"], "slug": after["slug"], "status": after["status"]} != immutable:
            raise RuntimeError(f"Unrelated field changed while correcting category for {product_id}")
        if [int(item["id"]) for item in after.get("categories", [])] != [category_id]:
            raise RuntimeError(f"Category verification failed for {product_id}")
        results.append({"product_id": product_id, "model": offer, "category": {"id": category_id, "name": category_name}, "result": "PASS"})
    (ROOT / "output" / "category-correction-audit.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    client = WooCommerceClient()
    categories = {int(item["id"]): item for item in client.get("products/categories", {"per_page": 100, "hide_empty": False})}
    for offer in OFFERS:
        product = json.loads((args.output_dir / offer / "processed-product.json").read_text(encoding="utf-8"))
        category = product["category"]
        if int(category["id"]) not in categories or categories[int(category["id"])]["name"] != category["name"]:
            raise RuntimeError(f"Existing category assertion failed for {offer}: {category}")
    category_results = correct_existing_categories(client)
    results = []
    for offer in OFFERS:
        product_dir = args.output_dir / offer
        product = json.loads((product_dir / "processed-product.json").read_text(encoding="utf-8"))
        media = upload_media(client, product_dir, product)
        parent, variations, bindings = create_or_resume(client, product_dir, product, media)
        results.append(verify_product(client, product_dir, product, parent, variations, bindings))
        product["woocommerce_uploaded"] = True
        product["woocommerce_product_id"] = int(parent["id"])
        product["woocommerce_status"] = "draft"
        (product_dir / "processed-product.json").write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"products": results, "category_corrections": category_results}
    (args.output_dir / "batch-woocommerce-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit("HARD STOP: use the fixed site runner.py entry")
