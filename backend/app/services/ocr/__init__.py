from app.services.ocr.base import OCREngine, OCRPage, OCRResult
from app.services.ocr.registry import available_engines, get_engine, register
from app.services.ocr import claude_ocr  # noqa: F401  imported for its @register side effect
from app.services.ocr import stub  # noqa: F401  imported for its @register side effect

__all__ = ["OCREngine", "OCRPage", "OCRResult", "register", "get_engine", "available_engines"]
