from datetime import datetime, timedelta

from opero_connectors.email_connector import EmailMessageDraft, EmailMessageSummary
from opero_connectors.mocks import (
    MockCalendarConnector,
    MockCRMConnector,
    MockDocumentConnector,
    MockEmailConnector,
)


async def test_mock_email_connector_never_actually_sends_and_records_the_draft() -> None:
    connector = MockEmailConnector()
    draft = EmailMessageDraft(to=["customer@example.com"], subject="Hi", body_text="Hello there")

    message_id = await connector.send_message(draft)

    assert message_id.startswith("mock-message-")
    assert connector.sent == [draft]


async def test_mock_email_connector_lists_seeded_messages() -> None:
    seed = [
        EmailMessageSummary(
            external_id="m1",
            thread_external_id="t1",
            sender="a@b.com",
            recipients=["me@example.com"],
            subject="Hi",
            snippet="...",
            body_text="Hello there, just checking in.",
            received_at=datetime(2026, 1, 1, 9, 0),
        )
    ]
    connector = MockEmailConnector(seed_messages=seed)

    messages = await connector.list_recent_messages()

    assert messages == seed


async def test_mock_calendar_connector_creates_and_lists_events_in_start_order() -> None:
    connector = MockCalendarConnector()
    now = datetime(2026, 1, 1, 9, 0)

    later = await connector.create_event(
        "Later meeting", now + timedelta(days=1), now + timedelta(days=1, hours=1), []
    )
    earlier = await connector.create_event("Earlier meeting", now, now + timedelta(hours=1), ["a@b.com"])

    events = await connector.list_upcoming_events()

    assert [e.external_id for e in events] == [earlier.external_id, later.external_id]


async def test_mock_crm_connector_upsert_is_idempotent_by_email() -> None:
    connector = MockCRMConnector()

    first = await connector.upsert_contact("Jane Doe", "jane@example.com", company="Acme")
    second = await connector.upsert_contact("Jane D.", "jane@example.com", company="Acme Inc")

    assert first.external_id == second.external_id
    found = await connector.find_contact_by_email("jane@example.com")
    assert found.name == "Jane D."


async def test_mock_crm_connector_returns_none_for_unknown_contact() -> None:
    connector = MockCRMConnector()

    assert await connector.find_contact_by_email("nobody@example.com") is None


async def test_mock_document_connector_round_trips_content() -> None:
    connector = MockDocumentConnector()

    stored = await connector.upload("policy.pdf", b"fake pdf bytes", "application/pdf")
    downloaded = await connector.download(stored.external_id)
    listed = await connector.list_documents()

    assert downloaded == b"fake pdf bytes"
    assert stored.size_bytes == len(b"fake pdf bytes")
    assert listed == [stored]


async def test_mock_document_connector_raises_for_unknown_id() -> None:
    connector = MockDocumentConnector()

    try:
        await connector.download("does-not-exist")
        raised = False
    except KeyError:
        raised = True

    assert raised
