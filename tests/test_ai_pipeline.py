from types import SimpleNamespace

from app.run_ai_image_pipeline import decide_from_model_outputs, write_acceptance_audit


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


def test_acceptance_audit_separates_mask_creation_from_inpainting(tmp_path):
    mask = tmp_path / "image_audit" / "ai_masks" / "001-mask.png"
    mask.parent.mkdir(parents=True)
    mask.write_bytes(b"mask")
    audit = {
        "offer_id": "582636594501",
        "created_at": "2026-09-04T00:00:00+00:00",
        "execution": {
            "paddleocr": {"executed": True, "detection_model": "PP-OCRv5"},
            "openclip": {"executed": True, "model": "ViT-B-32"},
            "inpainting": {
                "executed": True,
                "engine": "LaMa FP32 ONNX",
                "model": "Carve/LaMa-ONNX lama_fp32.onnx",
            },
        },
        "summary": {
            "source_count": 31,
            "sha_unique_count": 25,
            "deleted_count": 12,
            "final_kept_count": 13,
        },
        "records": [
            {
                "filename": "001.jpg",
                "ocr_text": ["watermark"],
                "text_coverage": 0.01,
                "classification": {"label": "product_photo", "confidence": 0.9},
                "keep": True,
                "decision_reason": "small watermark",
                "mask_file": "image_audit/ai_masks/001-mask.png",
                "inpainting_executed": True,
                "output_file": "processed_images/001.webp",
            },
            {
                "filename": "002.jpg",
                "ocr_text": [],
                "text_coverage": 0.0,
                "classification": {"label": "product_photo", "confidence": 0.8},
                "keep": True,
                "decision_reason": "clean product photo",
                "mask_file": "image_audit/ai_masks/missing-mask.png",
                "inpainting_executed": False,
                "output_file": "processed_images/002.webp",
            },
        ],
    }

    result = write_acceptance_audit(audit, tmp_path)

    expected_fields = {
        "filename",
        "ocr_text",
        "text_coverage",
        "classification",
        "keep_or_delete",
        "reason",
        "mask_generated",
        "inpainting_executed",
        "final_filename",
    }
    assert set(result["records"][0]) == expected_fields
    assert result["records"][0]["mask_generated"] is True
    assert result["records"][0]["inpainting_executed"] is True
    assert result["records"][1]["mask_generated"] is False
    assert result["records"][1]["inpainting_executed"] is False
    assert result["model_execution"]["paddleocr"]["actually_executed"] is True
    assert result["model_execution"]["openclip"]["actually_executed"] is True
    assert result["model_execution"]["inpainting"]["model_name"] == (
        "Carve/LaMa-ONNX lama_fp32.onnx"
    )
