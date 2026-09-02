"""Image pipeline contract.

Heavy OCR / vision / inpainting dependencies are intentionally adapters so the
web app can run separately from a GPU image worker.
"""

from dataclasses import dataclass
from io import BytesIO
from PIL import Image


@dataclass
class ImageDecision:
    keep: bool
    reason: str
    needs_inpainting: bool = False
    mask: object | None = None


DELETE_CLASSES = {
    "factory",
    "company_building",
    "staff",
    "certificate",
    "qr_code",
    "contact_card",
    "advertising_banner",
}


def decide_image(classification: str, text_coverage: float, watermark_on_product: bool) -> ImageDecision:
    if classification in DELETE_CLASSES:
        return ImageDecision(False, f"blocked class: {classification}")
    if text_coverage >= 0.35:
        return ImageDecision(False, "large text/watermark coverage")
    if watermark_on_product and text_coverage >= 0.15:
        return ImageDecision(False, "large watermark overlaps product")
    if 0 < text_coverage < 0.15:
        return ImageDecision(True, "small removable text/watermark", needs_inpainting=True)
    return ImageDecision(True, "clean product image")


def optimize_webp(image_bytes: bytes, max_edge: int = 1800, quality: int = 83) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, "WEBP", quality=quality, method=6, exif=b"")
    return output.getvalue()


class OCRAdapter:
    """TODO: PaddleOCR adapter: return text boxes + coverage + masks."""

    def analyze(self, image_bytes: bytes):
        raise NotImplementedError


class VisionClassifierAdapter:
    """TODO: OpenCLIP / vision model adapter for product-vs-company classification."""

    def classify(self, image_bytes: bytes):
        raise NotImplementedError


class InpaintingAdapter:
    """TODO: LaMa/IOPaint-compatible adapter. Mask first; do not crop first."""

    def inpaint(self, image_bytes: bytes, mask):
        raise NotImplementedError
