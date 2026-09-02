import os
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
        self.base_url = os.environ["WOOCOMMERCE_URL"].rstrip("/")
        self.key = os.environ["WOOCOMMERCE_CONSUMER_KEY"]
        self.secret = os.environ["WOOCOMMERCE_CONSUMER_SECRET"]

    def _request(self, method: str, path: str, json=None):
        response = requests.request(
            method,
            f"{self.base_url}/wp-json/wc/v3/{path.lstrip('/')}",
            auth=(self.key, self.secret),
            json=json,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def create_draft(self, product: Product):
        created = self._request("POST", "products", build_draft_payload(product))
        if product.variations:
            for variation in build_variation_payloads(product):
                self._request("POST", f"products/{created['id']}/variations", variation)
        return created
