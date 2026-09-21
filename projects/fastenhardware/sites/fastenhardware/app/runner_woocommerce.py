"""New-product REST adapter with durable writes and fail-closed publication.

Existing products are never rewritten by this runner. Only a draft created by
this runner's upload checkpoint may be resumed. No automatic retry of a POST
whose outcome is unknown.
"""
from __future__ import annotations

import html
import re
import time
from pathlib import Path

from .batch_upload_adaptive import build_attributes, metadata, verify_public_image, wp_request
from .core import calculate_sale_price
from .runner_content import canonical
from .runner_state import ReviewRequired, digest, file_hash, read, save, now
from .woocommerce import WooCommerceClient


def pages(client, path, extra=None):
    out, page = [], 1
    while True:
        items = client.get(path, {"per_page": 100, "page": page, **(extra or {})})
        out.extend(items)
        if len(items) < 100:
            return out
        page += 1


def identity(parent):
    meta = metadata(parent.get("meta_data", []))
    ids = set()
    for key in ("_1688_offer_id", "_1688_model"):
        match = re.fullmatch(r"(?:Model:\s*)?(\d+)", str(meta.get(key, "")))
        if match:
            ids.add(match.group(1))
    try:
        ids.add(canonical(meta.get("_1688_source_url")))
    except ValueError:
        pass
    for a in parent.get("attributes", []):
        if a.get("name", "").lower() == "model":
            for v in a.get("options", []):
                if str(v).isdigit():
                    ids.add(str(v))
    return ids


def payloads(product, records, media):
    top = [r for r in records if r["image_role"] in ("featured", "gallery")]
    detail = [r for r in records if r["image_role"] == "description"]
    desc = ["<p>" + html.escape(product["description_overview"]) + "</p>"]
    if product.get("description_specs"):
        desc.append("<h2>Specifications</h2><table><tbody>" + "".join(
            "<tr><th>" + html.escape(str(k)) + "</th><td>" + html.escape(str(v)) + "</td></tr>"
            for k, v in product["description_specs"].items()) + "</tbody></table>")
    for r in detail:
        item = media[r["final_sha256"]]
        desc.append('<figure style="max-width:900px;width:100%;margin:0 auto;"><img src="' + html.escape(item["src"], quote=True) + '" alt="' +
                    html.escape(product["title"], quote=True) + '" style="max-width:100%;height:auto;" loading="lazy"></figure>')
    desc.append("<p>Model: " + product["offer_id"] + "</p>")
    parent = dict(name=product["title"], slug=product["slug"], type="variable", status="draft",
                  description="\n".join(desc), short_description="<p>" + html.escape(product["short_description"]) + "</p>",
                  categories=[{"id": product["category"]["id"]}], attributes=build_attributes(product),
                  images=[{"id": media[r["final_sha256"]]["id"]} for r in top],
                  meta_data=[{"key": "_1688_offer_id", "value": product["offer_id"]},
                             {"key": "_1688_model", "value": product["model"]},
                             {"key": "_1688_source_url", "value": product["source_url"]},
                             {"key": "_1688_runner_fingerprint", "value": product["fingerprint"]}] +
                            [{"key": key, "value": product["seo"][field]} for key, field in
                             (("rank_math_title", "meta_title"), ("rank_math_description", "meta_description"),
                              ("rank_math_focus_keyword", "focus_keyword"))])
    parent["meta_data"].extend([{ "key":"1688 Offer ID", "value":product["offer_id"]},
                                {"key":"1688 Source URL", "value":product["source_url"]}])
    by_url = {r["source_image_url"]: r for r in records}
    variations, warnings = [], []
    for position, sku in enumerate(product["skus"]):
        if sku.get("source_sku_position") != position:
            raise ValueError("HARD STOP: SOURCE_SKU_ORDER_MISMATCH")
        price = str(calculate_sale_price(sku["source_price"]))
        if price != sku["sale_price"]:
            raise ValueError("FAIL_CURRENT_PRICE")
        row = dict(sku=str(sku["sku"]), regular_price=price, sale_price="", manage_stock=sku.get("stock") is not None,
                   attributes=[{"name": k, "option": v} for k, v in sku["attributes"].items()],
                   meta_data=[{"key": "_1688_" + key, "value": sku[key]} for key in
                              ("variation_id", "spec_id", "source_spec_id", "source_price", "sale_price") if sku.get(key) is not None])
        if sku.get("stock") is not None:
            row["stock_quantity"] = int(sku["stock"])
        exact = by_url.get(sku.get("image_url"))
        if exact:
            row["image"] = {"id": media[exact["final_sha256"]]["id"]}
        else:
            warnings.append("NO_DEDICATED_IMAGE: " + str(sku["sku"]))
        row["menu_order"] = position
        row["meta_data"].append({"key":"source_sku_position","value":position})
        if not row.get("image"):
            if not parent["images"]:
                raise ReviewRequired("PARENT_FEATURED_FALLBACK_MISSING")
            row["image"] = dict(parent["images"][0])
        variations.append(row)
    return parent, variations, warnings


def verify_saved(product, expected, expected_variations, parent, variations, check_http):
    offer = product["offer_id"]
    meta = metadata(parent.get("meta_data", []))
    failures = []
    if identity(parent) != {offer} or meta.get("_1688_source_url") != product["source_url"]:
        failures.append("IDENTITY_SOURCE_MISMATCH")
    if meta.get("_1688_model") != product["model"] or "Model: " + offer not in parent.get("description", ""):
        failures.append("MODEL_MISMATCH")
    for key in ("name", "slug", "type", "description", "short_description"):
        if parent.get(key) != expected[key]:
            failures.append("SAVED_" + key.upper() + "_MISMATCH")
    if {c["id"] for c in parent.get("categories", [])} != {product["category"]["id"]}:
        failures.append("CATEGORY_MISMATCH")
    if [i["id"] for i in parent.get("images", [])] != [i["id"] for i in expected["images"]]:
        failures.append("FEATURED_GALLERY_MISMATCH")
    for item in expected["meta_data"]:
        if meta.get(item["key"]) != item["value"]:
            failures.append("META_FIELD_MISMATCH:" + item["key"])
    actual = {v["sku"]: v for v in variations}
    if len(actual) != len(variations) or set(actual) != {v["sku"] for v in expected_variations}:
        failures.append("SKU_SET_MISMATCH")
    for v in expected_variations:
        live = actual.get(v["sku"], {})
        if live.get("regular_price") != v["regular_price"] or live.get("sale_price", ""):
            failures.append("PRICE_MISMATCH")
        if {a["name"]: a["option"] for a in live.get("attributes", [])} != {a["name"]: a["option"] for a in v["attributes"]}:
            failures.append("VARIATION_ATTRIBUTES_MISMATCH")
        if live.get("menu_order") != v["menu_order"]:
            failures.append("SOURCE_SKU_ORDER_MISMATCH")
        lm = metadata(live.get("meta_data", []))
        if any(lm.get(i["key"]) != i["value"] for i in v["meta_data"]):
            failures.append("VARIATION_SOURCE_IDS_MISMATCH")
        if v.get("image") and (live.get("image") or {}).get("id") != v["image"]["id"]:
            failures.append("VARIATION_IMAGE_MISMATCH")
    urls = [i["src"] for i in parent.get("images", [])]
    urls += re.findall(r'<img[^>]+src="([^"]+)"', parent.get("description", ""))
    urls += [v["image"]["src"] for v in variations if v.get("image")]
    checks = [check_http(html.unescape(url)) for url in dict.fromkeys(urls)]
    if not checks or not all(c["pass"] for c in checks):
        failures.append("HTTP_IMAGE_FAIL")
    if failures:
        raise ReviewRequired("REST_ACCEPTANCE_FAIL: " + ",".join(sorted(set(failures))))
    return dict(status="PASS", image_http=checks, product_id=parent["id"], sku_count=len(variations))


class Store:
    def __init__(self, client=None):
        self.client = client or WooCommerceClient()
        self.categories = pages(self.client, "products/categories", {"hide_empty": False})
        self.products = pages(self.client, "products", {"status": "any", "context": "edit"})
        self.write_count = 0

    def verify_rendered(self, product_id, expected_parent):
        document = wp_request(self.client, "GET", f"product/{product_id}",
                              params={"context": "edit", "_": str(time.time())}).json()
        if document.get("featured_media") != expected_parent["images"][0]["id"]:
            raise ReviewRequired("WORDPRESS_FEATURED_MEDIA_MISMATCH")
        urls = re.findall(r'<img[^>]+src=["\']([^"\']+)', document.get("content", {}).get("rendered", ""), re.I)
        intended = re.findall(r'<img[^>]+src=["\']([^"\']+)', expected_parent["description"], re.I)
        if len(urls) != len(intended):
            raise ReviewRequired("WORDPRESS_RENDERED_DESCRIPTION_IMAGE_COUNT_MISMATCH")
        results = [verify_public_image(html.unescape(u)) for u in urls]
        if not all(r["pass"] for r in results):
            raise ReviewRequired("WORDPRESS_RENDERED_BROKEN_IMAGE")
        return results

    def upload(self, product, image_result, folder, *, draft=False):
        if image_result.get("publication_qa") != "PASS":
            raise ReviewRequired("IMAGE_PUBLICATION_QA_NOT_PASS")
        offer = product["offer_id"]
        candidates = [p for p in self.products if offer in identity(p)]
        if len(candidates) > 1:
            raise ReviewRequired("WARNING_DUPLICATE_MAPPING")
        path = folder / "upload-checkpoint.json"
        state = read(path, {"offer_id": offer, "media": {}, "variations": {}, "writes": {}})
        if state["offer_id"] != offer:
            raise ValueError("CROSS_OFFER_UPLOAD_CHECKPOINT")
        if candidates and state.get("product_id") != candidates[0]["id"]:
            raise ReviewRequired("EXISTING_PRODUCT_NOT_OWNED_BY_RUNNER_CHECKPOINT; no update or duplicate create")
        if state.get("fingerprint") not in (None, product["fingerprint"]):
            raise ReviewRequired("UPLOAD_INPUT_CHANGED; reconcile existing draft before resuming")
        state["fingerprint"] = product["fingerprint"]

        def write_once(key, request):
            record = state["writes"].get(key)
            if record and record["status"] == "DONE":
                return record["result"]
            if record:
                raise ReviewRequired("UNCERTAIN_REMOTE_WRITE: " + key + "; reconcile, never retry POST blindly")
            state["writes"][key] = {"status": "IN_FLIGHT", "timestamp": now()}
            save(path, state)
            self.write_count += 1
            result = request()
            state["writes"][key] = {"status": "DONE", "timestamp": now(), "result": result}
            save(path, state)
            return result

        # Allocate our own unpublished target before media writes so every
        # attachment carries a real target ID, not an ambiguous future mapping.
        for r in image_result["records"]:
            if str(r["source_offer_id"]) != offer or file_hash(r["final_path"]) != r["final_sha256"]:
                raise ValueError("FAIL_IMAGE_PROVENANCE_OR_CHANGED_BYTES")
        stub = dict(name=product["title"], type="variable", status="draft", images=[],
                    description="<p>Model: " + offer + "</p>", meta_data=[
                        {"key": "_1688_offer_id", "value": offer},
                        {"key": "_1688_model", "value": product["model"]},
                        {"key": "_1688_source_url", "value": product["source_url"]},
                        {"key": "_1688_runner_fingerprint", "value": product["fingerprint"]}])
        parent = write_once("parent", lambda: self.client.post("products", stub))
        state["product_id"] = parent["id"]
        save(path, state)
        self.products = [p for p in self.products if p["id"] != parent["id"]] + [parent]
        live = self.client.get(f"products/{parent['id']}", {"context": "edit"})
        if identity(live) != {offer} or metadata(live.get("meta_data", [])).get("_1688_runner_fingerprint") != product["fingerprint"]:
            raise ReviewRequired("RESUME_TARGET_IDENTITY_MISMATCH")
        for r in image_result["records"]:
            if str(r["source_offer_id"]) != offer or file_hash(r["final_path"]) != r["final_sha256"]:
                raise ValueError("FAIL_IMAGE_PROVENANCE_OR_CHANGED_BYTES")
            sha = r["final_sha256"]
            r["woocommerce_product_id"] = parent["id"]
            save(folder / "image-upload-provenance.json", image_result["records"])
            def upload_image(r=r):
                with Path(r["final_path"]).open("rb") as stream:
                    item = wp_request(self.client, "POST", "media", files={"file":
                        (offer + "-" + product["slug"] + "-" + r["final_sha256"][:12] + ".webp", stream, "image/webp")},
                        data={"title": product["title"], "alt_text": product["title"], "post": parent["id"]}).json()
                return {"id": item["id"], "src": item["source_url"]}
            state["media"][sha] = write_once("media:" + sha, upload_image)
        parent_payload, variations_payload, warnings = payloads(product, image_result["records"], state["media"])
        write_once("parent-body", lambda: self.client.post(f"products/{parent['id']}", parent_payload))
        live = self.client.get("products/" + str(parent["id"]), {"context": "edit"})
        if identity(live) != {offer} or metadata(live.get("meta_data", [])).get("_1688_runner_fingerprint") != product["fingerprint"]:
            raise ReviewRequired("RESUME_TARGET_IDENTITY_MISMATCH")
        existing = pages(self.client, f"products/{parent['id']}/variations")
        existing_skus = {v["sku"] for v in existing}
        for v in variations_payload:
            key = "sku:" + v["sku"]
            if v["sku"] in existing_skus and key not in state["writes"]:
                raise ReviewRequired("UNEXPECTED_EXISTING_VARIATION")
            saved = write_once(key, lambda v=v: self.client.post(f"products/{parent['id']}/variations", v))
            state["variations"][v["sku"]] = saved["id"]
            save(path, state)
        live = self.client.get(f"products/{parent['id']}", {"context": "edit"})
        live_variations = pages(self.client, f"products/{parent['id']}/variations")
        before_publish = verify_saved(product, parent_payload, variations_payload, live, live_variations, verify_public_image)
        before_publish["rendered_image_http"] = self.verify_rendered(parent["id"], parent_payload)
        if not draft:
            from .site_guard import DOMAIN
            ui = read(folder / "backend-source-acceptance.json", {})
            if not (ui.get("site_url") == DOMAIN and ui.get("product_id") == parent["id"]
                    and ui.get("offer_id") == offer and ui.get("source_url") == product["source_url"]
                    and ui.get("model_visible") is True and ui.get("source_link_clicked") is True
                    and ui.get("status") == "PASS" and ui.get("fingerprint") == product["fingerprint"]):
                raise ReviewRequired("BACKEND_SOURCE_LINK_UI_ACCEPTANCE_REQUIRED")
        wanted = "draft" if draft else "publish"
        if live["status"] != wanted:
            if live["status"] != "draft":
                raise ReviewRequired("UNEXPECTED_REMOTE_STATUS; no status reversal")
            write_once("publish", lambda: self.client.post(f"products/{parent['id']}", {"status": wanted}))
        live = self.client.get(f"products/{parent['id']}", {"context": "edit"})
        final = verify_saved(product, parent_payload, variations_payload, live,
                             pages(self.client, f"products/{parent['id']}/variations"), verify_public_image)
        if live["status"] != wanted:
            raise ReviewRequired("FINAL_STATUS_MISMATCH")
        final["rendered_image_http"] = self.verify_rendered(parent["id"], parent_payload)
        for r in image_result["records"]:
            r["woocommerce_product_id"] = parent["id"]
        final.update(status=wanted, url=live["permalink"], warnings=warnings,
                     prepublication=before_publish, image_provenance=image_result["records"])
        save(folder / "final-rest-audit.json", final)
        return final
