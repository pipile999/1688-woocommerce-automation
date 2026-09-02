import argparse
import json

from dotenv import load_dotenv

from .cleaner import clean_description
from .core import extract_offer_id, validate_1688_url
from .models import Product
from .woocommerce import build_draft_payload


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--title", default="1688 Imported Product")
    parser.add_argument("--description", default="")
    args = parser.parse_args()

    if not validate_1688_url(args.url):
        raise SystemExit("Invalid 1688 product URL")

    product = Product(
        source_url=args.url,
        title=args.title,
        description=clean_description(args.description),
    )
    payload = build_draft_payload(product)

    print(f"Offer ID / Model: {extract_offer_id(args.url)}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
