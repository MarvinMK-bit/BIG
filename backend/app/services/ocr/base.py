from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OCRPage:
    page_number: int
    markdown: str
    confidence: float | None


@dataclass
class OCRResult:
    pages: list[OCRPage]
    engine_name: str
    engine_version: str | None
    raw_response: dict | None


class OCREngine(ABC):
    """Contract for OCR engines.

    Takes an image or document in, returns structured Markdown out, one
    page at a time, with a per-page confidence score where the engine
    provides one. Implementations must not leak provider-specific
    details beyond the OCRResult/OCRPage shape.
    """

    name: str

    @abstractmethod
    async def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        ...
