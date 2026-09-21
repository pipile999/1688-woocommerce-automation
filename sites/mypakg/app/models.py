from dataclasses import dataclass, field
from typing import Any


@dataclass
class Variation:
    sku: str
    source_price: float
    attributes: dict[str, str] = field(default_factory=dict)
    source_variant_id: str | None = None
    image_url: str | None = None


@dataclass
class Product:
    source_url: str
    title: str
    description: str = ""
    images: list[str] = field(default_factory=list)
    variations: list[Variation] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
