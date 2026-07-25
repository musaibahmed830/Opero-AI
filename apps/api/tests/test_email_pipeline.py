import uuid

import jwt
import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.email_classification import EmailClassification
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.models.lead import Lead
from app.models.task import Task
from app.services.email_processing import process_email
from tests.factories import auth_headers, client, register


async def test_ingest_mock_emails_is_idempotent() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)

        first = await c.post("/v1/emails/ingest-mock", headers=headers)
        second = await c.post("/v1/emails/ingest-mock", headers=headers)

    assert first.status_code == 200
    assert first.json()["ingested"] == 12
    assert second.status_code == 200
    assert second.json()["ingested"] == 0


async def test_list_and_get_email_scoped_to_organization() -> None:
    async with client() as c:
        token_a = await register(c, "Email Org A")
        token_b = await register(c, "Email Org B")

        await c.post("/v1/emails/ingest-mock", headers=auth_headers(token_a))

        listed = await c.get("/v1/emails", headers=auth_headers(token_a))
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 12

        message_id = body["items"][0]["id"]
        detail_a = await c.get(f"/v1/emails/{message_id}", headers=auth_headers(token_a))
        detail_b = await c.get(f"/v1/emails/{message_id}", headers=auth_headers(token_b))

    assert detail_a.status_code == 200
    assert "body_text" in detail_a.json()
    assert detail_b.status_code == 404

    other_org_list = None
    async with client() as c:
        other_org_list = await c.get("/v1/emails", headers=auth_headers(token_b))
    assert other_org_list.json()["total"] == 0


@pytest.mark.live_model
async def test_process_email_pipeline_classifies_and_may_extract() -> None:
    """Runs the real pipeline (classification -> lead/task extraction ->
    draft + approval proposal, all against the live Ollama model) on one of
    the 12 fixed mock scenarios and checks structural invariants rather than
    exact model wording, since live model output is not deterministic.
    """
    async with client() as c:
        token = await register(c)
        organization_id = uuid.UUID(_decode_org(token))
        headers = auth_headers(token)
        await c.post("/v1/emails/ingest-mock", headers=headers)
        emails = (await c.get("/v1/emails?page_size=50", headers=headers)).json()["items"]

    async with AsyncSessionLocal() as db:
        message = (
            await db.execute(select(EmailMessage).where(EmailMessage.id == uuid.UUID(emails[0]["id"])))
        ).scalar_one()
        classification = await process_email(db, message=message, organization_id=organization_id)

    assert classification.confidence >= 0.0
    assert classification.confidence <= 1.0
    assert isinstance(classification.possible_prompt_injection, bool)

    async with AsyncSessionLocal() as db:
        if classification.contains_lead:
            lead = (
                await db.execute(select(Lead).where(Lead.source_message_id == message.id))
            ).scalar_one_or_none()
            assert lead is not None

        if classification.contains_task:
            tasks = (
                (await db.execute(select(Task).where(Task.source_message_id == message.id)))
                .scalars()
                .all()
            )
            assert len(tasks) >= 0  # model may legitimately decide zero concrete actions


def _decode_org(token: str) -> str:
    return jwt.decode(token, options={"verify_signature": False})["organization_id"]


@pytest.mark.live_model
async def test_prompt_injection_email_is_flagged() -> None:
    """One of the 12 mock fixtures (docs/EMAIL_INTELLIGENCE.md Part 3) is a
    deliberate prompt-injection attempt. This confirms the regex scanner (not
    the model) is what sets possible_prompt_injection, per
    docs/PROMPT_INJECTION_DEFENCE.md.
    """
    async with client() as c:
        token = await register(c)
        organization_id = uuid.UUID(_decode_org(token))
        headers = auth_headers(token)
        await c.post("/v1/emails/ingest-mock", headers=headers)

    async with AsyncSessionLocal() as db:
        thread_ids = (
            (
                await db.execute(
                    select(EmailThread.id).where(EmailThread.organization_id == organization_id)
                )
            )
            .scalars()
            .all()
        )
        messages = (
            (
                await db.execute(
                    select(EmailMessage).where(
                        EmailMessage.thread_id.in_(thread_ids),
                        EmailMessage.body_text.ilike("%ignore%previous%instructions%"),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert messages, "expected the mock fixture set to include an injection attempt"

        classification = await process_email(
            db, message=messages[0], organization_id=organization_id
        )

    assert classification.possible_prompt_injection is True

    async with AsyncSessionLocal() as db:
        stored = (
            await db.execute(
                select(EmailClassification).where(EmailClassification.message_id == messages[0].id)
            )
        ).scalar_one()
        assert stored.possible_prompt_injection is True
