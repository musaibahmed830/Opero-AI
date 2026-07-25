"""Ingests Gmail messages into EmailThread/EmailMessage rows.

Two modes (docs/SYSTEM_ARCHITECTURE.md §2.4 / §3):
- First sync (`account.history_cursor is None`): backfill the most recent
  messages so there's something to ground drafts on immediately, then record
  the current historyId as the incremental-sync starting point.
- Subsequent syncs: walk Gmail's history API from the stored cursor forward,
  so we only fetch what's new rather than re-scanning the mailbox.
"""

import base64
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_account import EmailAccount
from app.models.email_message import EmailDirection, EmailMessage
from app.models.email_thread import EmailThread
from app.services.gmail_client import GmailAPIClient

INITIAL_BACKFILL_SIZE = 20


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_bodies(payload: dict) -> tuple[str, str | None]:
    text_body = ""
    html_body: str | None = None

    def walk(part: dict) -> None:
        nonlocal text_body, html_body
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")
        if body_data:
            if mime_type == "text/plain" and not text_body:
                text_body = _decode_body(body_data)
            elif mime_type == "text/html" and not html_body:
                html_body = _decode_body(body_data)
        for sub_part in part.get("parts") or []:
            walk(sub_part)

    walk(payload)
    return text_body, html_body


def _header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


async def _upsert_message(db: AsyncSession, account: EmailAccount, gmail_message: dict) -> bool:
    """Returns True if a new message row was created."""
    payload = gmail_message["payload"]
    headers = payload.get("headers", [])
    thread_gmail_id = gmail_message["threadId"]
    subject = _header(headers, "Subject")
    received_at = datetime.fromtimestamp(int(gmail_message["internalDate"]) / 1000, tz=UTC)

    result = await db.execute(
        select(EmailThread).where(
            EmailThread.email_account_id == account.id,
            EmailThread.provider_thread_id == thread_gmail_id,
        )
    )
    thread = result.scalar_one_or_none()

    if thread is None:
        thread = EmailThread(
            organization_id=account.organization_id,
            email_account_id=account.id,
            provider_thread_id=thread_gmail_id,
            subject=subject,
            last_message_at=received_at,
        )
        db.add(thread)
        await db.flush()
    elif received_at > thread.last_message_at:
        thread.last_message_at = received_at

    existing = await db.execute(
        select(EmailMessage.id).where(
            EmailMessage.thread_id == thread.id,
            EmailMessage.provider_message_id == gmail_message["id"],
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    text_body, html_body = _extract_bodies(payload)
    sender = _header(headers, "From")
    to_header = _header(headers, "To")
    recipients = [addr.strip() for addr in to_header.split(",") if addr.strip()]
    direction = (
        EmailDirection.OUTBOUND if account.email_address.lower() in sender.lower() else EmailDirection.INBOUND
    )

    db.add(
        EmailMessage(
            thread_id=thread.id,
            provider_message_id=gmail_message["id"],
            direction=direction,
            sender=sender,
            recipients=recipients,
            subject=subject,
            body_text=text_body,
            body_html=html_body,
            received_at=received_at,
        )
    )
    return True


async def sync_account(db: AsyncSession, account: EmailAccount, access_token: str) -> int:
    """Fetches new mail for `account` and upserts it. Returns count of messages ingested."""
    client = GmailAPIClient(access_token)
    ingested = 0

    if account.history_cursor is None:
        message_ids = await client.list_message_ids(max_results=INITIAL_BACKFILL_SIZE)
        for message_id in message_ids:
            message = await client.get_message(message_id)
            if await _upsert_message(db, account, message):
                ingested += 1
        profile = await client.get_profile()
        account.history_cursor = profile["historyId"]
    else:
        history = await client.list_history(account.history_cursor)
        for record in history.get("history", []):
            for added in record.get("messagesAdded", []):
                message = await client.get_message(added["message"]["id"])
                if await _upsert_message(db, account, message):
                    ingested += 1
        if "historyId" in history:
            account.history_cursor = history["historyId"]

    account.last_synced_at = datetime.now(UTC)
    await db.commit()
    return ingested
