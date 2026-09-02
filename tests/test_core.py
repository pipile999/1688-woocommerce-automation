from app.core import calculate_sale_price, extract_offer_id, validate_1688_url
from app.image_pipeline import decide_image


URL = "https://detail.1688.com/offer/605518859055.html?_t=1788338308253&spm=test"


def test_extract_offer_id():
    assert extract_offer_id(URL) == "605518859055"


def test_validate_url():
    assert validate_1688_url(URL)


def test_price_formula():
    assert str(calculate_sale_price(35)) == "7.46"


def test_large_text_image_deleted():
    assert not decide_image("product", 0.40, False).keep


def test_small_watermark_uses_inpainting():
    decision = decide_image("product", 0.08, False)
    assert decision.keep
    assert decision.needs_inpainting


def test_factory_deleted():
    assert not decide_image("factory", 0.0, False).keep
