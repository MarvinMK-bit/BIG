import asyncio
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.storage.base import StorageBackend, StoredFile
from app.services.storage.registry import register


@register
class LocalStorageBackend(StorageBackend):
    name = "local"

    def __init__(self) -> None:
        settings = get_settings()
        self.root = Path(settings.STORAGE_LOCAL_ROOT)

    def _path_for(self, key: str) -> Path:
        if not key or "/" in key or "\\" in key or ".." in key or Path(key).is_absolute():
            raise ValueError(f"Invalid storage key: {key!r}")

        root = self.root.resolve()
        candidate = (self.root / key).resolve()

        if candidate.parent != root:
            raise ValueError(f"Invalid storage key: {key!r}")

        return candidate

    async def save(self, file_bytes: bytes, *, filename: str, mime_type: str) -> StoredFile:
        extension = Path(filename).suffix
        key = f"{uuid.uuid4()}{extension}"

        def _write() -> None:
            self.root.mkdir(parents=True, exist_ok=True)
            self._path_for(key).write_bytes(file_bytes)

        await asyncio.to_thread(_write)

        return StoredFile(key=key, size_bytes=len(file_bytes), mime_type=mime_type)

    async def load(self, key: str) -> bytes:
        path = self._path_for(key)

        def _read() -> bytes:
            if not path.is_file():
                raise FileNotFoundError(f"No stored file for key {key!r}")
            return path.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path_for(key).unlink, True)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path_for(key).is_file)
