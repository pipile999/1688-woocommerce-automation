"""Executable OCR, OpenCLIP, LaMa, rembg, and quality-first WebP tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
import os

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


class RembgAdapter:
    """Persistent local rembg session for faithful product cutouts."""

    model_name = "isnet-general-use"

    def __init__(self, models_dir: Path):
        from rembg import new_session

        models_dir.mkdir(parents=True, exist_ok=True)
        os.environ["U2NET_HOME"] = str(models_dir.resolve())
        self.session = new_session(self.model_name)

    def cutout(self, image_bytes: bytes) -> Image.Image:
        from rembg import remove

        source = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
        result = remove(
            source,
            session=self.session,
            alpha_matting=False,
        ).convert("RGBA")
        alpha = result.getchannel("A").filter(ImageFilter.MedianFilter(3))
        alpha_array = np.asarray(alpha, dtype=np.uint8).copy()
        alpha_array[alpha_array < 18] = 0
        # Remove small disconnected foreground islands such as faint OCR/logo
        # remnants while retaining every substantial product component in a
        # multi-item composition.
        import cv2

        component_mask = (alpha_array > 0).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(component_mask, connectivity=8)
        minimum_area = max(64, round(source.width * source.height * 0.0008))
        for label in range(1, count):
            if int(stats[label, cv2.CC_STAT_AREA]) < minimum_area:
                alpha_array[labels == label] = 0
        alpha = Image.fromarray(alpha_array, mode="L")
        result.putalpha(alpha)
        if not alpha.getbbox():
            raise RuntimeError("rembg returned an empty foreground mask")
        return result

    def on_neutral_square(
        self,
        image_bytes: bytes,
        *,
        canvas_size: int = 1200,
        occupancy: float = 0.78,
        background: tuple[int, int, int] = (250, 250, 248),
    ) -> tuple[Image.Image, dict]:
        cutout = self.cutout(image_bytes)
        bbox = cutout.getchannel("A").getbbox()
        assert bbox is not None
        cutout = cutout.crop(bbox)
        target = max(1, round(canvas_size * occupancy))
        scale = min(target / max(cutout.size), 1.0)
        if scale < 1.0:
            cutout = cutout.resize(
                (max(1, round(cutout.width * scale)), max(1, round(cutout.height * scale))),
                Image.Resampling.LANCZOS,
            )
        canvas = Image.new("RGB", (canvas_size, canvas_size), background)
        offset = ((canvas_size - cutout.width) // 2, (canvas_size - cutout.height) // 2)
        canvas.paste(cutout, offset, cutout)
        occupied = max(cutout.width, cutout.height) / canvas_size
        return canvas, {
            "model": self.model_name,
            "canvas": [canvas_size, canvas_size],
            "foreground_dimensions": list(cutout.size),
            "foreground_occupancy": round(occupied, 4),
            "upscaled": False,
            "background_rgb": list(background),
        }


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


def _sharpness(image: Image.Image) -> float:
    import cv2

    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    # CV_64F doubles the working-set for no useful QA precision and can fail
    # late in long batch runs after the OCR/CLIP models have occupied RAM.
    # Float32 keeps the Laplacian metric stable while avoiding that spike.
    return float(cv2.Laplacian(gray, cv2.CV_32F).var(dtype=np.float32))


def _psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    error = float(np.mean((reference.astype(np.float32) - candidate.astype(np.float32)) ** 2))
    if error == 0:
        return 99.0
    return float(20.0 * np.log10(255.0 / np.sqrt(error)))


def adaptive_quality_webp(
    image: Image.Image,
    *,
    source_dimensions: tuple[int, int],
    source_filesize: int,
    max_edge: int | None = None,
    text_sensitive: bool = False,
) -> tuple[bytes, dict]:
    """Encode once from the finished master and reject visibly lossy candidates."""

    finished = ImageOps.exif_transpose(image).convert("RGB")
    if max_edge and max(finished.size) > max_edge:
        scale = max_edge / max(finished.size)
        finished = finished.resize(
            (max(1, round(finished.width * scale)), max(1, round(finished.height * scale))),
            Image.Resampling.LANCZOS,
        )
    reference = np.asarray(finished)
    reference_sharpness = _sharpness(finished)
    minimum_psnr = 40.0 if text_sensitive else 37.0
    minimum_sharpness_ratio = 0.86 if text_sensitive else 0.78
    selected = None
    attempts = []
    for quality in (86, 88, 90, 92, 94, 96):
        buffer = BytesIO()
        finished.save(buffer, "WEBP", quality=quality, method=6, exif=b"")
        payload = buffer.getvalue()
        decoded = Image.open(BytesIO(payload)).convert("RGB")
        candidate_sharpness = _sharpness(decoded)
        sharpness_ratio = candidate_sharpness / reference_sharpness if reference_sharpness else 1.0
        psnr = _psnr(reference, np.asarray(decoded))
        passed = psnr >= minimum_psnr and sharpness_ratio >= minimum_sharpness_ratio
        attempts.append(
            {
                "quality": quality,
                "psnr_db": round(psnr, 3),
                "sharpness_ratio": round(sharpness_ratio, 4),
                "pass": passed,
            }
        )
        if passed:
            selected = (payload, quality, psnr, sharpness_ratio, candidate_sharpness)
            break
    if selected is None:
        quality = 98
        buffer = BytesIO()
        finished.save(buffer, "WEBP", quality=quality, method=6, exif=b"")
        payload = buffer.getvalue()
        decoded = Image.open(BytesIO(payload)).convert("RGB")
        candidate_sharpness = _sharpness(decoded)
        sharpness_ratio = candidate_sharpness / reference_sharpness if reference_sharpness else 1.0
        psnr = _psnr(reference, np.asarray(decoded))
        passed = psnr >= minimum_psnr and sharpness_ratio >= minimum_sharpness_ratio
        attempts.append({"quality": quality, "psnr_db": round(psnr, 3), "sharpness_ratio": round(sharpness_ratio, 4), "pass": passed})
        if not passed:
            buffer = BytesIO()
            finished.save(buffer, "WEBP", lossless=True, method=6, exif=b"")
            payload = buffer.getvalue()
            decoded = Image.open(BytesIO(payload)).convert("RGB")
            candidate_sharpness = _sharpness(decoded)
            sharpness_ratio = candidate_sharpness / reference_sharpness if reference_sharpness else 1.0
            psnr = _psnr(reference, np.asarray(decoded))
            attempts.append({"quality": "lossless", "psnr_db": round(psnr, 3), "sharpness_ratio": round(sharpness_ratio, 4), "pass": True})
            selected = (payload, "lossless", psnr, sharpness_ratio, candidate_sharpness)
        else:
            selected = (payload, quality, psnr, sharpness_ratio, candidate_sharpness)
    payload, quality, psnr, sharpness_ratio, candidate_sharpness = selected
    return payload, {
        "source_width": int(source_dimensions[0]),
        "source_height": int(source_dimensions[1]),
        "processed_width": finished.width,
        "processed_height": finished.height,
        "source_filesize": int(source_filesize),
        "final_filesize": len(payload),
        "compression_ratio": round(len(payload) / source_filesize, 4) if source_filesize else None,
        "quality": quality,
        "psnr_db": round(psnr, 3),
        "source_processed_sharpness": round(reference_sharpness, 3),
        "final_sharpness": round(candidate_sharpness, 3),
        "sharpness_ratio": round(sharpness_ratio, 4),
        "sharpness_quality_check": "PASS",
        "text_sensitive": text_sensitive,
        "exif_removed": True,
        "upscaled": False,
        "attempts": attempts,
    }


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
        scale = min(1.0, 5000 / max(image.size), (16_000_000 / (image.width * image.height)) ** 0.5)
        analysis_image = image
        if scale < 1.0:
            analysis_image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        predictions = list(self.engine.predict(np.asarray(analysis_image)))
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
            points = [
                [int(round(x / scale)), int(round(y / scale))]
                for x, y in np.asarray(polygon).tolist()
            ]
            detections.append(OCRDetection(normalized_text, round(float(score), 6), points))

        mask = Image.new("L", analysis_image.size, 0)
        draw = ImageDraw.Draw(mask)
        for detection in detections:
            draw.polygon(
                [(round(point[0] * scale), round(point[1] * scale)) for point in detection.polygon],
                fill=255,
            )
        if detections:
            import cv2

            dilated = cv2.dilate(np.asarray(mask, dtype=np.uint8), np.ones((17, 17), np.uint8), iterations=1)
            mask = Image.fromarray(dilated, mode="L")
        coverage = float(np.count_nonzero(np.asarray(mask))) / float(mask.width * mask.height)
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
        "damaged_or_deformed": [
            "a badly edited product image with smeared patches, broken edges, blur, or artificial repair artifacts",
            "a deformed or stretched ecommerce product with visibly damaged cutout edges",
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
