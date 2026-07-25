import uuid
from datetime import datetime

from opero_connectors.calendar_connector import CalendarConnector, CalendarEvent


class MockCalendarConnector(CalendarConnector):
    def __init__(self, seed_events: list[CalendarEvent] | None = None) -> None:
        self._events = list(seed_events or [])

    async def list_upcoming_events(self, max_results: int = 20) -> list[CalendarEvent]:
        return sorted(self._events, key=lambda e: e.start_at)[:max_results]

    async def create_event(
        self, title: str, start_at: datetime, end_at: datetime, attendees: list[str]
    ) -> CalendarEvent:
        event = CalendarEvent(
            external_id=f"mock-event-{uuid.uuid4().hex[:12]}",
            title=title,
            start_at=start_at,
            end_at=end_at,
            attendees=attendees,
        )
        self._events.append(event)
        return event
