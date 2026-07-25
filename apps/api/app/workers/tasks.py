"""Background jobs (docs/DEVELOPMENT_ROADMAP.md Phase 3, "Background Jobs").

Every task takes IDs, never raw content/secrets — the task fetches what it
needs from the DB/object storage itself, so job payloads (visible in Redis,
in Celery's own logging) never carry a document's private contents or a
user's credentials.

Each task creates its own event loop via `asyncio.run()`: Celery's worker
pool is process/thread-based, not asyncio-native. But the app's DB engine
(app/core/database.py) is a module-level singleton whose pooled connections
are bound to whichever loop first used them — reused across task invocations
*within the same long-running worker process*, this hits the exact same
"attached to a different loop" bug documented in tests/conftest.py. The fix is
the same one: dispose the engine after every task, so the next task's fresh
`asyncio.run()` loop opens its own fresh connection.
"""

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models.document import Document, DocumentProcessingStatus
from app.models.email_classification import EmailClassification
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.workers.celery_app import app

logger = logging.getLogger("opero.workers")


async def _run_and_dispose(coro):
    try:
        return await coro
    finally:
        await engine.dispose()


def _run(coro):
    return asyncio.run(_run_and_dispose(coro))


async def _process_document(document_id: str) -> None:
    from app.services.document_ingestion import process_document

    async with AsyncSessionLocal() as db:
        document = await db.get(Document, uuid.UUID(document_id))
        if document is None:
            logger.warning("process_document_task: document %s not found", document_id)
            return
        # Idempotency: a retried or duplicate-delivered task should not
        # reprocess a document that already reached a terminal state.
        if document.processing_status in (
            DocumentProcessingStatus.READY,
            DocumentProcessingStatus.ARCHIVED,
        ):
            logger.info(
                "process_document_task: %s already %s, skipping", document_id, document.processing_status
            )
            return
        await process_document(db, document)


@app.task(
    name="opero_api.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def process_document_task(self, document_id: str) -> None:
    try:
        _run(_process_document(document_id))
    except Exception as exc:
        logger.exception("process_document_task failed for %s", document_id)
        raise self.retry(exc=exc) from exc


async def _process_email(message_id: str) -> None:
    from app.services.email_processing import process_email

    async with AsyncSessionLocal() as db:
        message = await db.get(EmailMessage, uuid.UUID(message_id))
        if message is None:
            logger.warning("process_email_task: message %s not found", message_id)
            return

        # Idempotency: a retried or duplicate-delivered task should not
        # re-classify (and re-propose a reply for) an already-processed email.
        existing = await db.execute(
            select(EmailClassification.id).where(EmailClassification.message_id == message.id)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("process_email_task: %s already classified, skipping", message_id)
            return

        organization_id = (
            await db.execute(
                select(EmailThread.organization_id).where(EmailThread.id == message.thread_id)
            )
        ).scalar_one()
        await process_email(db, message=message, organization_id=organization_id)


@app.task(
    name="opero_api.process_email",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def process_email_task(self, message_id: str) -> None:
    try:
        _run(_process_email(message_id))
    except Exception as exc:
        logger.exception("process_email_task failed for %s", message_id)
        raise self.retry(exc=exc) from exc
