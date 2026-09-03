"""Executable OCR, OpenCLIP classification, LaMa inpainting, and WebP tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


@dataclass
class ImageDecision:
    keep: bool
    reason: str
    needs_inpainting: bool = False
    mask: object | None = None


@dataclass
class OCRDetection:
    text: str
    score: float
    polygon: list[list[int]]


@dataclass
class OCRAnalysis:
    detections: list[OCRDetection]
    text_coverage: float
    mask: Image.Image

    def json_data(self) -> dict:
        return {
            "text": [item.text for item in self.detections],
            "text_coverage": round(self.text_coverage, 6),
            "detections": [asdict(item) for item in self.detections],
        }


@dataclass
class Classification:
    label: str
    confidence: float
    scores: dict[str, float]


DELETE_CLASSES = {
    "factory_or_company",
    "certificate_or_document",
    "qr_or_contact_card",
    "advertisement",
    "product_infographic",
    "factory",
    "company_building",
    "staff",
    "certificate",
    "qr_code",
    "contact_card",
    "advertising_banner",
}


def decide_image(
    classification: str,
    text_coverage: float,
    watermark_on_product: bool,
    *,
    has_text: bool | None = None,
) -> ImageDecision:
    if classification in DELETE_CLASSES:
        return ImageDecision(False, f"blocked class: {classification}")
    if text_coverage >= 0.12:
        return ImageDecision(False, "large text/watermark coverage")
    if watermark_on_product and text_coverage >= 0.08:
        return ImageDecision(False, "watermark overlaps product")
    detected_text = text_coverage > 0 if has_text is None else has_text
    if detected_text:
        return ImageDecision(True, "small removable text/watermark", needs_inpainting=True)
    return ImageDecision(True, "clean product image")


def optimize_webp(image_bytes: bytes, max_edge: int = 1800, quality: int = 83) -> bytes:
    image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
    width, height = image.size
    scale = max_edge / max(width, height)
    image = image.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, "WEBP", quality=quality, method=6, exif=b"")
    return output.getvalue()


class OCRAdapter:
    """PaddleOCR PP-OCRv5 mobile detector and recognizer running on CPU."""

    detection_model = "PP-OCRv5_mobile_det"
    recognition_model = "PP-OCRv5_mobile_rec"

    def __init__(self, min_score: float = 0.75):
        from paddleocr import PaddleOCR

        self.min_score = min_score
        self.engine = PaddleOCR(
            lang="ch",
            text_detection_model_name=self.detection_model,
            text_recognition_model_name=self.recognition_model,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
        )

    def analyze(self, image_bytes: bytes) -> OCRAnalysis:
        image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
        predictions = list(self.engine.predict(np.asarray(image)))
        payload = predictions[0].json if predictions else {"res": {}}
        result = payload.get("res", payload)
        texts = result.get("rec_texts", [])
        scores = result.get("rec_scores", [])
        polygons = result.get("rec_polys", result.get("dt_polys", []))

        detections = []
        for text, score, polygon in zip(texts, scores, polygons, strict=False):
            normalized_text = str(text).strip()
            valid_characters = sum(character.isalnum() for character in normalized_text)
            if float(score) < self.min_score or valid_characters < 2:
                continue
            points = [[int(round(x)), int(round(y))] for x, y in np.asarray(polygon).tolist()]
            detections.append(OCRDetection(normalized_text, round(float(score), 6), points))

        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        for detection in detections:
            draw.polygon([tuple(point) for point in detection.polygon], fill=255)
        if detections:
            mask = mask.filter(ImageFilter.MaxFilter(17))
        coverage = float(np.count_nonzero(np.asarray(mask))) / float(image.width * image.height)
        return OCRAnalysis(detections, coverage, mask)


class VisionClassifierAdapter:
    """OpenCLIP ViT-B-32 zero-shot image classifier running on CPU."""

    model_name = "ViT-B-32"
    pretrained = "laion2b_s34b_b79k"
    prompts = {
        "product_photo": [
            "a clean ecommerce product photo on a plain background",
            "a studio photograph showing only a consumer product",
            "a close-up product photo without promotional layout",
        ],
        "product_infographic": [
            "a product specification infographic with measurements and text labels",
            "an ecommerce product detail graphic with diagrams and annotations",
        ],
        "advertisement": [
            "an advertising banner with prices and promotional text",
            "a shop recommendation collage or product catalog advertisement",
        ],
        "factory_or_company": [
            "a factory interior, manufacturing workshop, company building, or staff photo",
            "a company promotion photo showing workers or manufacturing",
        ],
        "certificate_or_document": [
            "a certificate, license, newspaper, or official business document",
            "a photographed printed document rather than a product",
        ],
        "qr_or_contact_card": [
            "a QR code, business card, phone number, or contact information graphic",
            "a contact card containing a QR code or social media handle",
        ],
    }

    def __init__(self):
        import open_clip
        import torch

        self.torch = torch
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=self.pretrained, device="cpu"
        )
        self.model.eval()
        tokenizer = open_clip.get_tokenizer(self.model_name)
        self.labels = list(self.prompts)
        flat_prompts = [prompt for label in self.labels for prompt in self.prompts[label]]
        tokenized = tokenizer(flat_prompts)
        with torch.no_grad():
            features = self.model.encode_text(tokenized)
            features /= features.norm(dim=-1, keepdim=True)
        class_features = []
        offset = 0
        for label in self.labels:
            count = len(self.prompts[label])
            mean = features[offset : offset + count].mean(dim=0)
            class_features.append(mean / mean.norm())
            offset += count
        self.text_features = torch.stack(class_features)

    def classify(self, image_bytes: bytes) -> Classification:
        image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
        tensor = self.preprocess(image).unsqueeze(0)
        with self.torch.no_grad():
            features = self.model.encode_image(tensor)
            features /= features.norm(dim=-1, keepdim=True)
            probabilities = (100.0 * features @ self.text_features.T).softmax(dim=-1)[0]
        scores = {
            label: round(float(score), 6)
            for label, score in zip(self.labels, probabilities.tolist(), strict=True)
        }
        label = max(scores, key=scores.get)
        return Classification(label, scores[label], scores)


class InpaintingAdapter:
    """Local LaMa FP32 ONNX model; inference is mandatory and has no fallback."""

    model_name = "Carve/LaMa-ONNX lama_fp32.onnx"

    def __init__(self, model_path: Path):
        import onnxruntime as ort

        if not model_path.is_file():
            raise FileNotFoundError(f"LaMa model not found: {model_path}")
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    def inpaint(self, image_bytes: bytes, mask: Image.Image) -> bytes:
        source = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
        mask = mask.convert("L")
        width, height = source.size
        scale = 512 / max(width, height)
        resized_size = (round(width * scale), round(height * scale))
        resized = source.resize(resized_size, Image.Resampling.LANCZOS)
        resized_mask = mask.resize(resized_size, Image.Resampling.NEAREST)
        left = (512 - resized.width) // 2
        top = (512 - resized.height) // 2

        image_canvas = Image.new("RGB", (512, 512), "white")
        mask_canvas = Image.new("L", (512, 512), 0)
        image_canvas.paste(resized, (left, top))
        mask_canvas.paste(resized_mask, (left, top))

        image_array = np.asarray(image_canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
        mask_array = (np.asarray(mask_canvas, dtype=np.float32)[None, None] > 0).astype(np.float32)
        output = self.session.run(None, {"image": image_array, "mask": mask_array})[0][0]
        output = output.transpose(1, 2, 0)
        if float(output.max()) <= 2.0:
            output *= 255.0
        output_image = Image.fromarray(np.clip(output, 0, 255).astype(np.uint8), "RGB")
        output_image = output_image.crop((left, top, left + resized.width, top + resized.height))
        output_image = output_image.resize(source.size, Image.Resampling.LANCZOS)

        feathered = mask.filter(ImageFilter.GaussianBlur(1.2))
        result = Image.composite(output_image, source, feathered)
        buffer = BytesIO()
        result.save(buffer, "PNG")
        return buffer.getvalue()
