from app.services.ocr.base import OCREngine

_ENGINES: dict[str, type[OCREngine]] = {}


def get_engine(name: str) -> OCREngine:
    try:
        engine_cls = _ENGINES[name]
    except KeyError:
        available = ", ".join(sorted(_ENGINES)) or "none registered"
        raise ValueError(f"Unknown OCR engine {name!r}. Available engines: {available}") from None

    return engine_cls()


def register(engine_cls: type[OCREngine]) -> type[OCREngine]:
    name = getattr(engine_cls, "name", None)
    if not name:
        raise ValueError(f"{engine_cls!r} must define a non-empty 'name' to be registered")

    if name in _ENGINES:
        raise ValueError(f"OCR engine {name!r} is already registered")

    _ENGINES[name] = engine_cls
    return engine_cls


def available_engines() -> list[str]:
    return sorted(_ENGINES)
