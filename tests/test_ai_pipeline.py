from types import SimpleNamespace

from app.run_ai_image_pipeline import decide_from_model_outputs


def detection(text, polygon):
    return SimpleNamespace(text=text, polygon=polygon)


def test_ocr_infographic_marker_is_deleted():
    classification = SimpleNamespace(label="product_photo")
    ocr = SimpleNamespace(
        detections=[detection("PRODUCT ANALYSIS", [[1, 1], [100, 1], [100, 20], [1, 20]])],
        text_coverage=0.01,
    )
    keep, reason, needs_inpainting = decide_from_model_outputs(classification, ocr, 750, 750)
    assert not keep
    assert "PRODUCT ANALYSIS" in reason
    assert not needs_inpainting


def test_small_peripheral_ocr_text_uses_lama():
    classification = SimpleNamespace(label="product_photo")
    ocr = SimpleNamespace(
        detections=[detection("shop.example.com", [[500, 680], [730, 680], [730, 720], [500, 720]])],
        text_coverage=0.03,
    )
    assert decide_from_model_outputs(classification, ocr, 750, 750) == (
        True,
        "small peripheral text/watermark; LaMa inpainting required",
        True,
    )


def test_clean_product_photo_is_kept_without_inpainting():
    classification = SimpleNamespace(label="product_photo")
    ocr = SimpleNamespace(detections=[], text_coverage=0.0)
    assert decide_from_model_outputs(classification, ocr, 750, 750) == (
        True,
        "clean product photo; no OCR text detected",
        False,
    )
