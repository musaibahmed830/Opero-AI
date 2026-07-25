import base64
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.email_account import EmailAccount
from app.models.email_message import EmailDirection, EmailMessage
from app.models.email_thread import EmailThread
from app.models.integration import Integration, IntegrationProvider
from app.models.organization import Organization
from app.services.gmail_sync import _extract_bodies, _header, _upsert_message


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_header_lookup_is_case_insensitive() -> None:
    headers = [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]

    assert _header(headers, "subject") == "Hello"
    assert _header(headers, "FROM") == "a@b.com"
    assert _header(headers, "Missing") == ""


def test_extract_bodies_prefers_first_text_and_html_part() -> None:
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("plain body")}},
            {"mimeType": "text/html", "body": {"data": _b64("<p>html body</p>")}},
        ],
    }

    text, html = _extract_bodies(payload)

    assert text == "plain body"
    assert html == "<p>html body</p>"


def test_extract_bodies_handles_simple_non_multipart_message() -> None:
    payload = {"mimeType": "text/plain", "body": {"data": _b64("just text")}}

    text, html = _extract_bodies(payload)

    assert text == "just text"
    assert html is None


@pytest.fixture
async def organization_and_account():
    async with AsyncSessionLocal() as db:
        organization = Organization(name="Test Organization")
        db.add(organization)
        await db.flush()

        integration = Integration(organization_id=organization.id, provider=IntegrationProvider.GMAIL)
        db.add(integration)
        await db.flush()

        account = EmailAccount(
            organization_id=organization.id,
            integration_id=integration.id,
            email_address="me@example.com",
            refresh_token_encrypted="unused-in-this-test",
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        yield db, account

        await db.delete(await db.get(Organization, organization.id))
        await db.commit()


def _fake_gmail_message(message_id: str, thread_id: str, sender: str, subject: str) -> dict:
    return {
        "id": message_id,
        "threadId": thread_id,
        "internalDate": str(int(datetime.now(UTC).timestamp() * 1000)),
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "To", "value": "me@example.com"},
            ],
            "mimeType": "text/plain",
            "body": {"data": _b64(f"body of {message_id}")},
        },
    }


async def test_upsert_message_creates_thread_and_message(organization_and_account) -> None:
    db, account = organization_and_account
    message = _fake_gmail_message("msg-1", "thread-1", "customer@example.com", "Question about pricing")

    created = await _upsert_message(db, account, message)
    await db.commit()

    assert created is True

    thread = (
        await db.execute(select(EmailThread).where(EmailThread.provider_thread_id == "thread-1"))
    ).scalar_one()
    assert thread.subject == "Question about pricing"

    stored_message = (
        await db.execute(select(EmailMessage).where(EmailMessage.provider_message_id == "msg-1"))
    ).scalar_one()
    assert stored_message.direction == EmailDirection.INBOUND
    assert stored_message.body_text == "body of msg-1"


async def test_upsert_message_is_idempotent_on_replay(organization_and_account) -> None:
    db, account = organization_and_account
    message = _fake_gmail_message("msg-2", "thread-2", "customer@example.com", "Hi")

    first = await _upsert_message(db, account, message)
    await db.commit()
    second = await _upsert_message(db, account, message)
    await db.commit()

    assert first is True
    assert second is False

    count = len(
        (
            await db.execute(select(EmailMessage).where(EmailMessage.provider_message_id == "msg-2"))
        )
        .scalars()
        .all()
    )
    assert count == 1


async def test_upsert_message_classifies_outbound_direction(organization_and_account) -> None:
    db, account = organization_and_account
    message = _fake_gmail_message("msg-3", "thread-3", "me@example.com", "Re: Question")

    await _upsert_message(db, account, message)
    await db.commit()

    stored_message = (
        await db.execute(select(EmailMessage).where(EmailMessage.provider_message_id == "msg-3"))
    ).scalar_one()
    assert stored_message.direction == EmailDirection.OUTBOUND
