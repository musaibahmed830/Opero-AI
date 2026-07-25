import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentProcessingStatus


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    mime_type: str
    file_size: int
    processing_status: DocumentProcessingStatus
    processing_error: str | None
    uploaded_at: datetime
    processed_at: datetime | None
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class DuplicateDocumentResponse(BaseModel):
    error: str = "duplicate_document"
    detail: str
    existing_document_id: uuid.UUID
