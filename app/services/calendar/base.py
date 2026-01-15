from typing import Protocol

from app.domain.schemas.calendar import CalendarEvent


class CalendarClient(Protocol):
    def upsert_event(self, calendar_event: CalendarEvent) -> str:
        ...

    def delete_event(self, calendar_event_id: str) -> None:
        ...
