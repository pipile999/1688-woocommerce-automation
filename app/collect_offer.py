import argparse
import json
from pathlib import Path

from .collector import CollectionBlocked, download_images, fetch_offer_html, parse_offer_html, write_diagnostic
from .core import extract_offer_id


def main():
    parser = argparse.ArgumentParser(description="Collect one 1688 offer without uploading to WooCommerce")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    offer_id = extract_offer_id(args.url)
    output_file = Path(args.output_dir) / f"{offer_id}.json"
    try:
        product = parse_offer_html(fetch_offer_html(args.url), args.url)
        image_dir = output_file.parent / offer_id / "raw_images"
        product["raw_images"] = download_images(product["images"], image_dir)
        product["status"] = "success"
        product["woocommerce_uploaded"] = False
    except CollectionBlocked as exc:
        write_diagnostic(args.url, output_file, str(exc))
        raise SystemExit(f"1688 collection blocked: {exc}; diagnostic: {output_file}") from exc

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_file)


if __name__ == "__main__":
    main()
