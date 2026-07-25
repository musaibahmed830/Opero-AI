import uuid

from opero_connectors.document_connector import DocumentConnector, StoredDocument


class MockDocumentConnector(DocumentConnector):
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._metadata: dict[str, StoredDocument] = {}

    async def upload(self, filename: str, content: bytes, content_type: str) -> StoredDocument:
        external_id = f"mock-doc-{uuid.uuid4().hex[:12]}"
        document = StoredDocument(
            external_id=external_id, filename=filename, content_type=content_type, size_bytes=len(content)
        )
        self._store[external_id] = content
        self._metadata[external_id] = document
        return document

    async def download(self, external_id: str) -> bytes:
        if external_id not in self._store:
            raise KeyError(f"No document with id {external_id}")
        return self._store[external_id]

    async def list_documents(self) -> list[StoredDocument]:
        return list(self._metadata.values())
