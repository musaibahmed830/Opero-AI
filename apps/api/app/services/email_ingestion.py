"""Mock email ingestion (docs/EMAIL_INTELLIGENCE.md "Email ingestion").

Uses the `EmailConnector` interface (`services/connectors`) exclusively via
`MockEmailConnector` — no real Gmail/Outlook credentials are touched in this
phase. Ingested messages land in the same `EmailAccount`/`EmailThread`/
`EmailMessage` tables the real Gmail sync (`app/services/gmail_sync.py`) uses,
distinguished by `EmailAccount.provider == EmailProvider.MOCK`, so downstream
classification/extraction/drafting code has exactly one code path regardless
of where the mail came from.
"""

import uuid
from datetime import UTC, datetime

from opero_connectors.mocks import MockEmailConnector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret
from app.models.audit_log import AuditActorType, AuditLog
from app.models.email_account import EmailAccount, EmailProvider
from app.models.email_message import EmailDirection, EmailMessage
from app.models.email_thread import EmailThread
from app.models.integration import Integration, IntegrationProvider
from app.services.mock_email_fixtures import build_mock_email_fixtures


async def ensure_mock_email_account(db: AsyncSession, organization_id: uuid.UUID) -> EmailAccount:
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.organization_id == organization_id, EmailAccount.provider == EmailProvider.MOCK
        )
    )
    account = result.scalar_one_or_none()
    if account is not None:
        return account

    integration = Integration(organization_id=organization_id, provider=IntegrationProvider.MOCK)
    db.add(integration)
    await db.flush()

    account = EmailAccount(
        organization_id=organization_id,
        integration_id=integration.id,
        provider=EmailProvider.MOCK,
        email_address=f"mock-inbox+{organization_id.hex[:8]}@opero-demo.example",
        refresh_token_encrypted=encrypt_secret("unused-for-mock-accounts"),
    )
    db.add(account)
    await db.flush()
    return account


async def ingest_mock_emails(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Fetches the fixed set of mock fixtures and ingests any not already
    present (deduplicated by provider_message_id, docs/SECURITY_MODEL.md
    §"Duplicate email prevention"). Returns the count of newly ingested
    messages — calling this twice ingests zero the second time.
    """
    account = await ensure_mock_email_account(db, organization_id)
    connector = MockEmailConnector(seed_messages=build_mock_email_fixtures())
    messages = await connector.list_recent_messages(max_results=100)

    ingested = 0
    for message in messages:
        thread_result = await db.execute(
            select(EmailThread).where(
                EmailThread.email_account_id == account.id,
                EmailThread.provider_thread_id == message.thread_external_id,
            )
        )
        thread = thread_result.scalar_one_or_none()
        if thread is None:
            thread = EmailThread(
                organization_id=organization_id,
                email_account_id=account.id,
                provider_thread_id=message.thread_external_id,
                subject=message.subject,
                last_message_at=message.received_at,
            )
            db.add(thread)
            await db.flush()
        elif message.received_at > thread.last_message_at:
            thread.last_message_at = message.received_at

        existing = await db.execute(
            select(EmailMessage.id).where(
                EmailMessage.thread_id == thread.id,
                EmailMessage.provider_message_id == message.external_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(
            EmailMessage(
                thread_id=thread.id,
                provider_message_id=message.external_id,
                direction=EmailDirection.INBOUND,
                sender=message.sender,
                recipients=message.recipients,
                subject=message.subject,
                body_text=message.body_text,
                received_at=message.received_at,
            )
        )
        ingested += 1

    account.last_synced_at = datetime.now(UTC)

    if ingested:
        db.add(
            AuditLog(
                organization_id=organization_id,
                actor_type=AuditActorType.SYSTEM,
                actor_id=None,
                action="email.ingested",
                resource_type="email_account",
                resource_id=account.id,
                audit_metadata={"ingested_count": ingested},
            )
        )
    await db.commit()
    return ingested
