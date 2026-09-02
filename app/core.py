import re
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse


def extract_offer_id(url: str) -> str:
    """Extract the numeric 1688 offer id from a detail URL."""
    match = re.search(r"/offer/(\d+)\.html", url)
    if not match:
        raise ValueError("Unsupported 1688 URL: offer ID not found")
    return match.group(1)


def calculate_sale_price(source_price, price_divisor="0.7", currency_divisor="6.7") -> Decimal:
    """Apply the seller's fixed pricing formula: source / 0.7 / 6.7."""
    price = Decimal(str(source_price))
    result = price / Decimal(str(price_divisor)) / Decimal(str(currency_divisor))
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_1688_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.endswith("1688.com") and bool(
        re.search(r"/offer/\d+\.html", parsed.path)
    )


def model_line(url: str) -> str:
    return f"Model: {extract_offer_id(url)}"
