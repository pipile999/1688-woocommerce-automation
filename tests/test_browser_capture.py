import json

from app.finalize_browser_capture import parse_detail_payload


def test_parse_detail_payload():
    payload = {"content": '<div>description<img src="https://example.com/a.jpg"></div>'}
    description, images = parse_detail_payload("var offer_details=" + json.dumps(payload) + ";")
    assert "description" in description
    assert images == ["https://example.com/a.jpg"]
