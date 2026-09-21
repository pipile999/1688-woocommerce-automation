import os
from pathlib import Path
from urllib.parse import quote

import requests

from .core import calculate_sale_price, extract_offer_id
from .models import Product


def build_draft_payload(product: Product) -> dict:
    offer_id = extract_offer_id(product.source_url)
    is_variable = bool(product.variations)

    description = product.description.strip()
    model = f"Model: {offer_id}"
    if model not in description:
        description = f"{description}\n\n{model}".strip()

    payload = {
        "name": product.title,
        "type": "variable" if is_variable else "simple",
        "status": "draft",
        "description": description,
        "meta_data": [
            {"key": "_1688_offer_id", "value": offer_id},
            {"key": "_1688_source_url", "value": product.source_url},
        ],
    }

    if product.images:
        payload["images"] = [{"src": url} for url in product.images]

    if is_variable:
        attribute_names = sorted({k for v in product.variations for k in v.attributes})
        payload["attributes"] = [
            {
                "name": name,
                "visible": True,
                "variation": True,
                "options": sorted({v.attributes[name] for v in product.variations if name in v.attributes}),
            }
            for name in attribute_names
        ]

    return payload


def build_variation_payloads(product: Product) -> list[dict]:
    """Preserve SKU and attribute combinations exactly; only calculate price."""
    result = []
    for variation in product.variations:
        item = {
            "sku": variation.sku,
            "regular_price": str(calculate_sale_price(variation.source_price)),
            "attributes": [
                {"name": name, "option": value} for name, value in variation.attributes.items()
            ],
            "meta_data": [],
        }
        if variation.source_variant_id:
            item["meta_data"].append(
                {"key": "_1688_source_variant_id", "value": variation.source_variant_id}
            )
        if variation.image_url:
            item["image"] = {"src": variation.image_url}
        result.append(item)
    return result


class WooCommerceClient:
    def __init__(self):
        from .site_guard import load_credentials, DOMAIN
        load_credentials()
        self.base_url = DOMAIN
        self.key = os.environ["WOOCOMMERCE_CONSUMER_KEY"]
        self.secret = os.environ["WOOCOMMERCE_CONSUMER_SECRET"]

    def _request(self, method: str, path: str, json=None, params=None, timeout=300):
        from .site_guard import endpoint
        endpoint(self.base_url, "wc", method, path)
        response = requests.request(
            method,
            f"{self.base_url}/wp-json/wc/v3/{path.lstrip('/')}",
            auth=(self.key, self.secret),
            json=json,
            params=params,
            timeout=timeout,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise ValueError("HARD STOP: STORE_REDIRECT")
        response.raise_for_status()
        return response.json()

    def get(self, path: str, params=None):
        return self._request("GET", path, params=params, timeout=60)

    def post(self, path: str, payload: dict):
        return self._request("POST", path, json=payload)

    def create_draft(self, product: Product):
        created = self._request("POST", "products", build_draft_payload(product))
        if product.variations:
            for variation in build_variation_payloads(product):
                self._request("POST", f"products/{created['id']}/variations", variation)
        return created


def _ordered_unique(values):
    return list(dict.fromkeys(str(value) for value in values))


def build_processed_image_urls(product: dict, image_base_url: str) -> list[dict]:
    """Map only processed WebP paths to public URLs WooCommerce can sideload."""
    result = []
    for position, relative_path in enumerate(product["images"]):
        path = Path(relative_path)
        if path.parts[:1] != ("processed_images",) or path.suffix.lower() != ".webp":
            raise ValueError(f"Only processed_images WebP files are allowed: {relative_path}")
        encoded_path = "/".join(quote(part) for part in path.parts)
        result.append(
            {
                "src": f"{image_base_url.rstrip('/')}/{encoded_path}",
                "name": f"{product['offer_id']}-{path.stem}",
                "alt": product["title"],
                "position": position,
            }
        )
    return result


def build_processed_draft_payload(product: dict, image_base_url: str) -> dict:
    offer_id = str(product["offer_id"])
    expected_model = f"Model: {offer_id}"
    if product.get("model") != expected_model:
        raise ValueError(f"Model must be exactly {expected_model}")
    if expected_model not in product["description"]:
        raise ValueError("Processed description does not display the required Model")
    if not product.get("skus"):
        raise ValueError("Processed product has no SKUs")

    variation_names = _ordered_unique(
        name for sku in product["skus"] for name in sku["attributes"]
    )
    attributes = []
    for name in variation_names:
        attributes.append(
            {
                "name": name,
                "visible": True,
                "variation": True,
                "options": _ordered_unique(
                    sku["attributes"][name]
                    for sku in product["skus"]
                    if name in sku["attributes"]
                ),
            }
        )

    attributes.append(
        {
            "name": "Model",
            "visible": True,
            "variation": False,
            "options": [offer_id],
        }
    )
    existing_names = set(variation_names) | {"Model"}
    for group in ("decisionCpv", "normalCpv"):
        for attribute in product.get("attributes", {}).get(group, []):
            name = attribute["name"]
            if name in existing_names:
                continue
            attributes.append(
                {
                    "name": name,
                    "visible": True,
                    "variation": False,
                    "options": _ordered_unique(attribute.get("values", [])),
                }
            )
            existing_names.add(name)

    return {
        "name": product["title"],
        "type": "variable",
        "status": "draft",
        "description": product["description"],
        "attributes": attributes,
        "images": build_processed_image_urls(product, image_base_url),
        "meta_data": [
            {"key": "_1688_offer_id", "value": offer_id},
            {"key": "_1688_source_url", "value": product["source_url"]},
            {"key": "_1688_model", "value": expected_model},
        ],
    }


def build_processed_variation_payloads(product: dict) -> list[dict]:
    """Preserve source SKU/variation/spec IDs and use the precomputed sale price."""
    result = []
    for sku in product["skus"]:
        price = str(sku["sale_price"])
        payload = {
            "sku": str(sku["sku"]),
            "regular_price": price,
            "manage_stock": True,
            "stock_quantity": int(sku.get("stock") or 0),
            "attributes": [
                {"name": name, "option": value}
                for name, value in sku["attributes"].items()
            ],
            "meta_data": [
                {"key": "_1688_variation_id", "value": str(sku["variation_id"])},
                {"key": "_1688_spec_id", "value": str(sku["spec_id"])},
                {"key": "_1688_source_price", "value": str(sku["source_price"])},
                {"key": "_1688_sale_price", "value": price},
                {
                    "key": "_1688_minimum_order_quantity",
                    "value": str(sku.get("minimum_order_quantity", "")),
                },
                {"key": "_1688_package", "value": sku.get("package", {})},
            ],
        }
        result.append(payload)
    return result
