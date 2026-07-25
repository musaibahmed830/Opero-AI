import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.email_classification import EmailCategory, EmailClassification, EmailPriority
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.models.lead import Lead
from app.models.task import Task
from app.schemas.email import (
    EmailClassificationResponse,
    EmailMessageDetailResponse,
    EmailMessageResponse,
    IngestMockEmailsResponse,
    ProcessEmailResponse,
)
from app.schemas.lead import LeadResponse
from app.schemas.pagination import PageParams, PaginatedResponse
from app.schemas.task import TaskResponse
from app.services.email_ingestion import ingest_mock_emails
from app.services.rbac import require_permission
from app.workers.tasks import process_email_task

router = APIRouter(prefix="/emails", tags=["emails"])


@router.post("/ingest-mock", response_model=IngestMockEmailsResponse)
async def ingest_mock(
    current_user: AuthenticatedUser = Depends(require_permission("email.send")),
    db: AsyncSession = Depends(get_db),
) -> IngestMockEmailsResponse:
    """Ingests the fixed set of mock fixtures (docs/EMAIL_INTELLIGENCE.md Part
    3) — no real Gmail/Outlook connection exists yet. Does not itself run the
    classification pipeline; call `POST /emails/{id}/process` (or the demo
    seed script) to do that.
    """
    ingested = await ingest_mock_emails(db, uuid.UUID(current_user.organization_id))
    return IngestMockEmailsResponse(ingested=ingested)


async def _get_scoped_message(
    db: AsyncSession, message_id: uuid.UUID, organization_id: uuid.UUID
) -> EmailMessage:
    result = await db.execute(
        select(EmailMessage)
        .join(EmailThread, EmailMessage.thread_id == EmailThread.id)
        .where(EmailMessage.id == message_id, EmailThread.organization_id == organization_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email message not found.")
    return message


@router.get("", response_model=PaginatedResponse[EmailMessageResponse])
async def list_emails(
    category: EmailCategory | None = Query(default=None),
    priority: EmailPriority | None = Query(default=None),
    requires_reply: bool | None = Query(default=None),
    received_after: datetime | None = Query(default=None),
    received_before: datetime | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_permission("email.read")),
    db: AsyncSession = Depends(get_db),
    pagination: PageParams = Depends(),
) -> PaginatedResponse:
    conditions = [EmailThread.organization_id == uuid.UUID(current_user.organization_id)]
    if category is not None:
        conditions.append(EmailClassification.category == category)
    if priority is not None:
        conditions.append(EmailClassification.priority == priority)
    if requires_reply is not None:
        conditions.append(EmailClassification.requires_reply == requires_reply)
    if received_after is not None:
        conditions.append(EmailMessage.received_at >= received_after)
    if received_before is not None:
        conditions.append(EmailMessage.received_at <= received_before)

    def _base_query(select_clause):
        return (
            select_clause.select_from(EmailMessage)
            .join(EmailThread, EmailMessage.thread_id == EmailThread.id)
            .outerjoin(EmailClassification, EmailClassification.message_id == EmailMessage.id)
            .where(*conditions)
        )

    total = (await db.execute(_base_query(select(func.count(EmailMessage.id.distinct()))))).scalar_one()
    result = await db.execute(
        _base_query(select(EmailMessage))
        .order_by(EmailMessage.received_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    messages = list(result.scalars().unique().all())

    classifications_result = await db.execute(
        select(EmailClassification).where(
            EmailClassification.message_id.in_([m.id for m in messages])
        )
    )
    classification_by_message = {c.message_id: c for c in classifications_result.scalars().all()}

    items = [
        EmailMessageResponse(
            id=message.id,
            thread_id=message.thread_id,
            sender=message.sender,
            recipients=message.recipients,
            subject=message.subject,
            received_at=message.received_at,
            classification=(
                EmailClassificationResponse.model_validate(classification_by_message[message.id])
                if message.id in classification_by_message
                else None
            ),
        )
        for message in messages
    ]

    return PaginatedResponse(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/{message_id}", response_model=EmailMessageDetailResponse)
async def get_email(
    message_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("email.read")),
    db: AsyncSession = Depends(get_db),
) -> EmailMessageDetailResponse:
    message = await _get_scoped_message(db, message_id, uuid.UUID(current_user.organization_id))

    classification = (
        await db.execute(
            select(EmailClassification).where(EmailClassification.message_id == message.id)
        )
    ).scalar_one_or_none()

    leads = (
        (
            await db.execute(
                select(Lead)
                .options(selectinload(Lead.contact))
                .where(Lead.source_message_id == message.id)
            )
        )
        .scalars()
        .all()
    )
    tasks = (
        (await db.execute(select(Task).where(Task.source_message_id == message.id).order_by(Task.created_at)))
        .scalars()
        .all()
    )

    return EmailMessageDetailResponse(
        id=message.id,
        thread_id=message.thread_id,
        sender=message.sender,
        recipients=message.recipients,
        subject=message.subject,
        received_at=message.received_at,
        body_text=message.body_text,
        classification=(
            EmailClassificationResponse.model_validate(classification) if classification else None
        ),
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        tasks=[TaskResponse.model_validate(task) for task in tasks],
    )


@router.post("/{message_id}/process", response_model=ProcessEmailResponse)
async def process_email_endpoint(
    message_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("email.send")),
    db: AsyncSession = Depends(get_db),
) -> ProcessEmailResponse:
    """Enqueues the full pipeline for one message: classify -> extract lead/
    tasks (if flagged) -> generate a reply draft and propose it for approval
    (if a reply is warranted). Idempotent — a message that already has a
    classification is skipped (app/workers/tasks.py::_process_email).
    """
    await _get_scoped_message(db, message_id, uuid.UUID(current_user.organization_id))
    process_email_task.delay(str(message_id))
    return ProcessEmailResponse()
