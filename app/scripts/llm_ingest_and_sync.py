from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.db.session import get_session
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.mapper import event_to_calendar_event
from app.services.llm.client import generate_kids_events_munich
from app.services.llm.parse import parse_kids_events


def main() -> None:
    raw_events = generate_kids_events_munich()
    parsed_events = parse_kids_events(raw_events)

    generated_count = len(raw_events)
    persisted_count = 0
    synced_count = 0

    tz = ZoneInfo("Europe/Berlin")
    session_gen = get_session()
    session = next(session_gen)
    try:
        client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)

        for item in parsed_events:
            event = Event(
                title=item["title"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                location=item["location"],
                description=item["description"],
                source_url=item["source_url"],
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            persisted_count += 1

            calendar_event = event_to_calendar_event(event)
            google_event_id = client.upsert_event(calendar_event)

            calendar_sync = CalendarSync(
                event_id=event.id,
                provider="google",
                calendar_event_id=google_event_id,
                synced_at=datetime.now(tz=tz),
            )
            session.add(calendar_sync)
            session.commit()
            synced_count += 1
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    print(f"Events generated: {generated_count}")
    print(f"Events persisted: {persisted_count}")
    print(f"Events synced: {synced_count}")


if __name__ == "__main__":
    main()
