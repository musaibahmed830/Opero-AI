import io
import uuid

import jwt
import pytest

from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentProcessingStatus
from app.models.document_chunk import EMBEDDING_DIM, DocumentChunk
from app.services.document_ingestion import process_document
from tests.factories import auth_headers, client, register


def _txt_file(content: str, filename: str = "policy.txt"):
    return {"file": (filename, io.BytesIO(content.encode()), "text/plain")}


async def test_ask_with_no_documents_returns_insufficient_evidence() -> None:
    """No chunks retrieved -> the RAG service short-circuits with zero model
    calls (app/services/rag.py), so this is deterministic and fast.
    """
    async with client() as c:
        token = await register(c)
        response = await c.post(
            "/v1/knowledge/ask",
            headers=auth_headers(token),
            json={"question": "What is our refund policy?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_evidence"] is True
    assert body["retrieved_chunks"] == []


async def _seed_ready_document_with_chunk(organization_id: uuid.UUID, content: str) -> None:
    """Inserts a READY document + chunk with a fixed placeholder embedding,
    bypassing the real extraction/embedding pipeline — used for isolation
    tests that don't need the live model to prove the point.
    """
    async with AsyncSessionLocal() as db:
        document = Document(
            organization_id=organization_id,
            title="policy.txt",
            original_filename="policy.txt",
            safe_filename=f"{uuid.uuid4()}.txt",
            mime_type="text/plain",
            file_size=len(content),
            checksum=uuid.uuid4().hex,
            storage_path="unused",
            processing_status=DocumentProcessingStatus.READY,
        )
        db.add(document)
        await db.flush()
        db.add(
            DocumentChunk(
                document_id=document.id,
                organization_id=organization_id,
                chunk_index=0,
                content=content,
                embedding=[0.1] * EMBEDDING_DIM,
            )
        )
        await db.commit()


async def test_search_not_visible_across_organizations() -> None:
    async with client() as c:
        token_a = await register(c, "Knowledge Org A")
        token_b = await register(c, "Knowledge Org B")

        organization_a = uuid.UUID(
            jwt.decode(token_a, options={"verify_signature": False})["organization_id"]
        )
        await _seed_ready_document_with_chunk(organization_a, "Our refund policy allows 30-day returns.")

        results_b = await c.get(
            "/v1/knowledge/search", headers=auth_headers(token_b), params={"query": "refund"}
        )

    assert results_b.status_code == 200
    assert results_b.json() == []


@pytest.mark.live_model
async def test_ask_grounds_answer_in_uploaded_document_with_citation() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)
        uploaded = (
            await c.post(
                "/v1/documents",
                headers=headers,
                files=_txt_file(
                    "Our refund policy allows returns within 30 days of purchase for a full refund."
                ),
            )
        ).json()

        async with AsyncSessionLocal() as db:
            document = await db.get(Document, uuid.UUID(uploaded["id"]))
            await process_document(db, document)

        response = await c.post(
            "/v1/knowledge/ask",
            headers=headers,
            json={"question": "How many days do customers have to return an item?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert len(body["retrieved_chunks"]) > 0
    assert "30" in body["answer"]
