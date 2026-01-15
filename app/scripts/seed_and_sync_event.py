from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.db.session import get_session
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.mapper import event_to_calendar_event

SEED_EVENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def main() -> None:
    tz = ZoneInfo("Europe/Berlin")
    start_time = datetime.now(tz=tz) + timedelta(hours=2)
    end_time = start_time + timedelta(minutes=90)

    session_gen = get_session()
    session = next(session_gen)
    try:
        event = session.get(Event, SEED_EVENT_ID)
        if event is None:
            event = Event(id=SEED_EVENT_ID)
            session.add(event)

        event.title = "PLANZ Seeded Kids Event"
        event.start_time = start_time
        event.end_time = end_time
        event.location = "Marienplatz, 80331 München, Germany"
        event.description = "Seeded test event for PLANZ DB -> Calendar flow."
        event.source_url = "https://example.com"

        session.commit()
        session.refresh(event)

        calendar_sync = session.scalar(
            select(CalendarSync).where(CalendarSync.event_id == event.id)
        )

        calendar_event = event_to_calendar_event(event)
        if calendar_sync and calendar_sync.calendar_event_id:
            calendar_event = calendar_event.model_copy(
                update={"google_event_id": calendar_sync.calendar_event_id}
            )

        client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)
        google_event_id = client.upsert_event(calendar_event)

        if calendar_sync is None:
            calendar_sync = CalendarSync(
                event_id=event.id,
                provider="google",
                calendar_event_id=google_event_id,
                synced_at=datetime.now(tz=tz),
            )
            session.add(calendar_sync)
        else:
            calendar_sync.calendar_event_id = google_event_id
            calendar_sync.synced_at = datetime.now(tz=tz)

        session.commit()

        print(f"DB event id: {event.id}")
        print(f"Google calendar event id: {google_event_id}")
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
