"""Email connector interface.

The real Gmail integration (apps/api/app/services/gmail_client.py,
gmail_sync.py) predates this formal interface and already does real,
tested OAuth + REST work against Gmail — see docs/IMPLEMENTATION_STATUS.md for
the note on formally adapting it to this protocol as follow-up, not a Phase 2
blocker. This interface exists so the rest of the system (and its tests) can
depend on a connector shape instead of a concrete provider, per the founder's
"safe interfaces + mock connectors" instruction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EmailMessageDraft:
    to: list[str]
    subject: str
    body_text: str


@dataclass(frozen=True)
class EmailMessageSummary:
    """Phase 3 (docs/EMAIL_INTELLIGENCE.md) extended this with the fields a
    real ingestion pipeline needs (body, recipients, timestamp) — a real Gmail
    connector's "list" call is typically lighter (id + snippet only, full body
    fetched separately per message), but the mock connector has no such cost
    tradeoff to make, so it returns full detail directly and skips a
    round-trip that would exist for no reason here.
    """

    external_id: str
    thread_external_id: str
    sender: str
    recipients: list[str]
    subject: str
    snippet: str
    body_text: str
    received_at: datetime


class EmailConnector(ABC):
    @abstractmethod
    async def list_recent_messages(self, max_results: int = 20) -> list[EmailMessageSummary]: ...

    @abstractmethod
    async def send_message(self, draft: EmailMessageDraft) -> str:
        """Sends a message and returns the provider's message id.

        This is transport only — it has no opinion on the approval workflow
        (docs/SECURITY_MODEL.md §5). Callers must gate this behind an approved
        ApprovalRequest; the connector itself doesn't check that.
        """
        ...
