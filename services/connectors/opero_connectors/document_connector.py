from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredDocument:
    external_id: str
    filename: str
    content_type: str
    size_bytes: int


class DocumentConnector(ABC):
    @abstractmethod
    async def upload(self, filename: str, content: bytes, content_type: str) -> StoredDocument: ...

    @abstractmethod
    async def download(self, external_id: str) -> bytes: ...

    @abstractmethod
    async def list_documents(self) -> list[StoredDocument]: ...
