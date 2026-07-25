from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CalendarEvent:
    external_id: str
    title: str
    start_at: datetime
    end_at: datetime
    attendees: list[str]


class CalendarConnector(ABC):
    @abstractmethod
    async def list_upcoming_events(self, max_results: int = 20) -> list[CalendarEvent]: ...

    @abstractmethod
    async def create_event(
        self, title: str, start_at: datetime, end_at: datetime, attendees: list[str]
    ) -> CalendarEvent: ...
