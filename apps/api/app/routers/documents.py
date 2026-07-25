import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.document import Document, DocumentProcessingStatus
from app.schemas.document import DocumentResponse
from app.schemas.pagination import PageParams, PaginatedResponse
from app.services.document_ingestion import (
    DuplicateDocumentError,
    archive_document,
    create_document,
)
from app.services.document_validation import FileTooLargeError, UnsupportedFileTypeError
from app.services.rbac import require_permission
from app.workers.tasks import process_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_permission("documents.write")),
    db: AsyncSession = Depends(get_db),
) -> Document:
    content = await file.read()
    try:
        document = await create_document(
            db,
            organization_id=uuid.UUID(current_user.organization_id),
            uploaded_by=uuid.UUID(current_user.subject),
            original_filename=file.filename or "unnamed",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_document",
                "detail": str(exc),
                "existing_document_id": str(exc.existing_document_id),
            },
        ) from exc
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    process_document_task.delay(str(document.id))
    return document


@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    status_filter: DocumentProcessingStatus | None = Query(default=None, alias="status"),
    mime_type: str | None = Query(default=None),
    uploaded_after: datetime | None = Query(default=None),
    uploaded_before: datetime | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_permission("documents.read")),
    db: AsyncSession = Depends(get_db),
    pagination: PageParams = Depends(),
) -> PaginatedResponse:
    conditions = [Document.organization_id == uuid.UUID(current_user.organization_id)]
    if status_filter is not None:
        conditions.append(Document.processing_status == status_filter)
    if mime_type is not None:
        conditions.append(Document.mime_type == mime_type)
    if uploaded_after is not None:
        conditions.append(Document.uploaded_at >= uploaded_after)
    if uploaded_before is not None:
        conditions.append(Document.uploaded_at <= uploaded_before)

    total = (
        await db.execute(select(func.count()).select_from(Document).where(*conditions))
    ).scalar_one()
    result = await db.execute(
        select(Document)
        .where(*conditions)
        .order_by(Document.uploaded_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    documents = list(result.scalars().all())

    return PaginatedResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def _get_scoped_document(
    db: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID
) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.organization_id == organization_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("documents.read")),
    db: AsyncSession = Depends(get_db),
) -> Document:
    return await _get_scoped_document(db, document_id, uuid.UUID(current_user.organization_id))


@router.post("/{document_id}/archive", response_model=DocumentResponse)
async def archive_document_endpoint(
    document_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("documents.write")),
    db: AsyncSession = Depends(get_db),
) -> Document:
    document = await _get_scoped_document(db, document_id, uuid.UUID(current_user.organization_id))
    return await archive_document(db, document, archived_by=uuid.UUID(current_user.subject))
