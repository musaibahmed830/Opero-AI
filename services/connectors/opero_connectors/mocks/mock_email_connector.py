import uuid

from opero_connectors.email_connector import EmailConnector, EmailMessageDraft, EmailMessageSummary


class MockEmailConnector(EmailConnector):
    """In-memory only — never sends a real email or makes a network call. Used
    for local development and tests when no real Gmail account is connected
    (docs/MVP_SCOPE.md: "safe mock connectors where credentials are unavailable").
    """

    def __init__(self, seed_messages: list[EmailMessageSummary] | None = None) -> None:
        self._messages = list(seed_messages or [])
        self.sent: list[EmailMessageDraft] = []

    async def list_recent_messages(self, max_results: int = 20) -> list[EmailMessageSummary]:
        return self._messages[:max_results]

    async def send_message(self, draft: EmailMessageDraft) -> str:
        self.sent.append(draft)
        return f"mock-message-{uuid.uuid4().hex[:12]}"
