from app.services.storage.base import StorageBackend

_BACKENDS: dict[str, type[StorageBackend]] = {}


def get_backend(name: str) -> StorageBackend:
    try:
        backend_cls = _BACKENDS[name]
    except KeyError:
        available = ", ".join(sorted(_BACKENDS)) or "none registered"
        raise ValueError(f"Unknown storage backend {name!r}. Available backends: {available}") from None

    return backend_cls()


def register(backend_cls: type[StorageBackend]) -> type[StorageBackend]:
    name = getattr(backend_cls, "name", None)
    if not name:
        raise ValueError(f"{backend_cls!r} must define a non-empty 'name' to be registered")

    if name in _BACKENDS:
        raise ValueError(f"Storage backend {name!r} is already registered")

    _BACKENDS[name] = backend_cls
    return backend_cls


def available_backends() -> list[str]:
    return sorted(_BACKENDS)
