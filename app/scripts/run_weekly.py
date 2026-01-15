from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.db.session import get_session
from app.scripts.extract_events import main as extract_events
from app.scripts.fetch_sources import main as fetch_sources
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.sync_events import sync_unsynced_events


def main() -> None:
    fetch_sources()
    extract_events()

    now = datetime.now(tz=timezone.utc)
    session_gen = get_session()
    session = next(session_gen)
    try:
        client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)
        synced = sync_unsynced_events(session, client, now=now)
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    print(f"Events synced: {synced}")


if __name__ == "__main__":
    main()
