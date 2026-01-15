from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.db.session import get_session
from app.scripts.extract_events import run_extract_events
from app.scripts.fetch_sources import run_fetch_sources
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.sync_events import sync_unsynced_events


def main() -> None:
    fetched_ok, fetched_error = run_fetch_sources()
    _, extracted_created = run_extract_events()

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

    print(f"Fetched OK: {fetched_ok}")
    print(f"Fetched errors: {fetched_error}")
    print(f"Events created: {extracted_created}")
    print(f"Events synced: {synced}")


if __name__ == "__main__":
    main()
