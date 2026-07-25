"""Semantic search over document chunks (docs/KNOWLEDGE_SYSTEM.md "Knowledge search").

Every query is filtered by `organization_id` at the SQL level — never applied
as an after-the-fetch check — so there is no code path where a chunk from
another organization can appear in results (docs/SECURITY_MODEL.md §4).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentProcessingStatus
from app.models.document_chunk import DocumentChunk
from app.services.ai_provider import get_model_provider


@dataclass(frozen=True)
class SearchResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    similarity: float


async def search_knowledge(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query_text: str,
    top_k: int,
    similarity_threshold: float,
    document_id: uuid.UUID | None = None,
    mime_type: str | None = None,
    uploaded_after: datetime | None = None,
    uploaded_before: datetime | None = None,
) -> list[SearchResult]:
    provider = get_model_provider()
    query_embedding = (await provider.embed([query_text]))[0]

    distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)

    conditions = [
        DocumentChunk.organization_id == organization_id,
        DocumentChunk.embedding.is_not(None),
        Document.processing_status == DocumentProcessingStatus.READY,
    ]
    if document_id is not None:
        conditions.append(DocumentChunk.document_id == document_id)
    if mime_type is not None:
        conditions.append(Document.mime_type == mime_type)
    if uploaded_after is not None:
        conditions.append(Document.uploaded_at >= uploaded_after)
    if uploaded_before is not None:
        conditions.append(Document.uploaded_at <= uploaded_before)

    query = (
        select(DocumentChunk, Document, distance_expr.label("distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(*conditions)
        .order_by(distance_expr)
        .limit(top_k)
    )
    rows = (await db.execute(query)).all()

    results = []
    for chunk, document, distance in rows:
        similarity = 1.0 - float(distance)
        if similarity < similarity_threshold:
            continue
        results.append(
            SearchResult(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity=similarity,
            )
        )
    return results
