from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StoredFile:
    key: str
    size_bytes: int
    mime_type: str


class StorageBackend(ABC):
    """Contract for file storage backends.

    Bytes in, an opaque key out. Callers persist that key and use it to
    load, check, or delete the file later — never the caller's own
    filename or path assumptions, which are backend-specific.
    """

    name: str

    @abstractmethod
    async def save(self, file_bytes: bytes, *, filename: str, mime_type: str) -> StoredFile:
        ...

    @abstractmethod
    async def load(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...
