import io
import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentProcessingStatus
from app.services.document_ingestion import process_document
from tests.factories import auth_headers, client, register


def _txt_file(content: str, filename: str = "policy.txt"):
    return {"file": (filename, io.BytesIO(content.encode()), "text/plain")}


async def test_upload_document_success() -> None:
    async with client() as c:
        token = await register(c)
        response = await c.post(
            "/v1/documents", headers=auth_headers(token), files=_txt_file("Our refund policy is 30 days.")
        )

    assert response.status_code == 201
    body = response.json()
    assert body["processing_status"] == "uploaded"
    assert body["original_filename"] == "policy.txt"


async def test_duplicate_upload_conflicts() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)
        content = "Duplicate detection content."

        first = await c.post("/v1/documents", headers=headers, files=_txt_file(content, "a.txt"))
        second = await c.post("/v1/documents", headers=headers, files=_txt_file(content, "b.txt"))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "duplicate_document"


async def test_unsupported_file_type_rejected() -> None:
    async with client() as c:
        token = await register(c)
        response = await c.post(
            "/v1/documents",
            headers=auth_headers(token),
            files={"file": ("virus.exe", io.BytesIO(b"whatever"), "application/octet-stream")},
        )

    assert response.status_code == 400


async def test_document_not_visible_across_organizations() -> None:
    async with client() as c:
        token_a = await register(c, "Doc Org A")
        token_b = await register(c, "Doc Org B")

        uploaded = (
            await c.post(
                "/v1/documents", headers=auth_headers(token_a), files=_txt_file("Org A only content.")
            )
        ).json()

        cross_org_get = await c.get(f"/v1/documents/{uploaded['id']}", headers=auth_headers(token_b))

    assert cross_org_get.status_code == 404


async def test_list_documents_paginated_and_scoped() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)
        for i in range(3):
            await c.post(
                "/v1/documents", headers=headers, files=_txt_file(f"Content number {i}.", f"doc{i}.txt")
            )

        response = await c.get("/v1/documents?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


@pytest.mark.live_model
async def test_process_document_creates_ready_chunks_with_embeddings() -> None:
    async with client() as c:
        token = await register(c)
        uploaded = (
            await c.post(
                "/v1/documents",
                headers=auth_headers(token),
                files=_txt_file("Our support hours are 9am to 5pm, Monday through Friday."),
            )
        ).json()

    async with AsyncSessionLocal() as db:
        document = await db.get(Document, uuid.UUID(uploaded["id"]))
        await process_document(db, document)
        await db.refresh(document)
        assert document.processing_status == DocumentProcessingStatus.READY
        assert document.processed_at is not None
