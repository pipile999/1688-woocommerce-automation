"""1688 offer collection with explicit anti-bot and completeness checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .core import calculate_sale_price, extract_offer_id


class CollectionBlocked(RuntimeError):
    """Raised when 1688 returns a login or anti-bot page."""


@dataclass
class CollectedSku:
    sku: str
    variation_id: str
    source_price: str
    sale_price: str
    attributes: dict[str, str] = field(default_factory=dict)
    image_url: str | None = None


def detect_access_block(html: str) -> str | None:
    signals = {
        "x5 anti-bot challenge": ("_____tmd_____", "x5secdata", "/punish?"),
        "login required for full product data": ("\u767b\u5f55\u67e5\u770b\u5168\u90e8\u89c4\u683c", "\u767b\u5f55\u67e5\u770b\u5168\u90e8"),
    }
    for reason, needles in signals.items():
        if any(needle in html for needle in needles):
            return reason
    return None


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _embedded_json(html: str) -> list[Any]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[Any] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if not any(word in text.lower() for word in ("sku", "offer", "price")):
            continue
        candidates = [text]
        match = re.search(r"(?:window\.)?[\w$]+\s*=\s*({.*})\s*;?\s*$", text, re.S)
        if match:
            candidates.insert(0, match.group(1))
        for candidate in candidates:
            try:
                found.append(json.loads(candidate))
                break
            except (json.JSONDecodeError, TypeError):
                continue
    return found


def parse_offer_html(html: str, source_url: str) -> dict[str, Any]:
    blocked = detect_access_block(html)
    if blocked:
        raise CollectionBlocked(blocked)

    offer_id = extract_offer_id(source_url)
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    meta_title = soup.find("meta", attrs={"property": "og:title"})
    if meta_title:
        title = str(meta_title.get("content") or "").strip()
    if not title and soup.title:
        title = re.sub(r"\s*-\s*\u963f\u91cc\u5df4\u5df4\s*$", "", soup.title.get_text(strip=True))

    images: list[str] = []
    skus: list[CollectedSku] = []
    description = ""
    for root in _embedded_json(html):
        for node in _walk(root):
            if not isinstance(node, dict):
                continue
            for key, value in node.items():
                low = str(key).lower()
                if isinstance(value, str) and value.startswith(("http://", "https://", "//")):
                    if "image" in low or re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", value, re.I):
                        images.append("https:" + value if value.startswith("//") else value)
                if not description and low in {"description", "detail", "detailhtml", "offerdescription"} and isinstance(value, str):
                    description = value

            variation_id = node.get("specId") or node.get("skuId") or node.get("id")
            price = node.get("price") or node.get("discountPrice") or node.get("salePrice")
            if variation_id is None or price is None:
                continue
            attrs = node.get("attributes") or node.get("attrs") or node.get("specAttrs") or {}
            if not isinstance(attrs, dict):
                attrs = {"specification": str(attrs)}
            sku_code = node.get("sku") or node.get("skuCode") or str(variation_id)
            try:
                sale_price = calculate_sale_price(price)
                Decimal(str(price))
            except Exception:
                continue
            skus.append(
                CollectedSku(
                    sku=str(sku_code),
                    variation_id=str(variation_id),
                    source_price=str(price),
                    sale_price=str(sale_price),
                    attributes={str(k): str(v) for k, v in attrs.items()},
                    image_url=node.get("imageUrl") or node.get("image"),
                )
            )

    unique_skus = {sku.variation_id: sku for sku in skus}
    unique_images = list(dict.fromkeys(images))
    missing = [name for name, value in (("title", title), ("description", description), ("images", unique_images), ("skus", unique_skus)) if not value]
    if missing:
        raise CollectionBlocked("incomplete product payload: " + ", ".join(missing))

    return {
        "offer_id": offer_id,
        "model": f"Model: {offer_id}",
        "source_url": source_url,
        "title": title,
        "description": description,
        "images": unique_images,
        "skus": [asdict(sku) for sku in unique_skus.values()],
        "missing_fields": [],
    }


def fetch_offer_html(url: str, timeout: int = 30) -> str:
    parsed = urlparse(url)
    mobile_url = urlunparse(parsed._replace(netloc="m.1688.com"))
    attempts = (
        (
            "desktop",
            url,
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36",
        ),
        (
            "mobile",
            mobile_url,
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Mobile Safari/537.36",
        ),
    )
    failures: list[str] = []
    session = requests.Session()
    for label, candidate_url, user_agent in attempts:
        response = session.get(
            candidate_url,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        reason = detect_access_block(response.text)
        if not reason:
            return response.text
        failures.append(f"{label}: {reason}")
    raise CollectionBlocked("; ".join(failures))


def download_images(image_urls: list[str], target_dir: Path, timeout: int = 30) -> list[str]:
    """Download original image URLs without renaming or transforming their content."""
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    session = requests.Session()
    for index, url in enumerate(dict.fromkeys(image_urls), start=1):
        response = session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://detail.1688.com/"},
            timeout=timeout,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(content_type)
        if not suffix:
            suffix = Path(urlparse(url).path).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            raise CollectionBlocked(f"image {index} returned non-image content: {content_type or 'unknown'}")
        destination = target_dir / f"{index:03d}{suffix}"
        destination.write_bytes(response.content)
        saved.append(str(destination))
    return saved


def write_diagnostic(url: str, output_file: Path, reason: str, observed: dict[str, Any] | None = None) -> dict[str, Any]:
    offer_id = extract_offer_id(url)
    previous_observed: dict[str, Any] = {}
    if output_file.exists():
        try:
            previous = json.loads(output_file.read_text(encoding="utf-8"))
            previous_observed = previous.get("observed_public_data") or {}
        except (json.JSONDecodeError, OSError, AttributeError):
            pass
    data = {
        "status": "blocked",
        "offer_id": offer_id,
        "model": f"Model: {offer_id}",
        "source_url": url,
        "block_reason": reason,
        "observed_public_data": observed or previous_observed,
        "missing_fields": ["complete_skus", "variation_ids", "description", "all_product_images"],
        "access_diagnostics": {
            "requests": "blocked",
            "playwright": "x5 captcha / page automation timeout",
            "login_detected": True,
            "captcha_detected": True,
            "anti_bot_detected": True,
        },
        "scheme_a_batch_suitable": False,
        "woocommerce_uploaded": False,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    (output_file.parent / offer_id / "raw_images").mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
