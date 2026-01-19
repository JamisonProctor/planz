from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any, List

from app.config import settings
from app.core.env import load_env
from app.logging import configure_logging
from app.services.calendar.google_calendar_service import GoogleCalendarClient


def is_planz_event(event: dict[str, Any], force_legacy: bool = False) -> bool:
    extended = event.get("extendedProperties", {}) or {}
    private = extended.get("private", {}) or {}
    if str(private.get("planz", "")).lower() == "true":
        return True
    if not force_legacy:
        return False
    summary = (event.get("summary") or "").lower()
    description = (event.get("description") or "").lower()
    url = (event.get("htmlLink") or "").lower()
    if summary.startswith("[plz]"):
        return True
    if "planz" in description:
        return True
    if "utm_source=openai" in url or "utm_source=openai" in description:
        return True
    return False


def filter_planz_events(events: List[dict[str, Any]], force_legacy: bool = False) -> List[dict[str, Any]]:
    return [event for event in events if is_planz_event(event, force_legacy=force_legacy)]


def wipe_planz_events(client: GoogleCalendarClient, days: int, dry_run: bool, force_legacy: bool = False) -> None:
    now = datetime.now(tz=timezone.utc)
    time_min = (now - timedelta(days=days)).isoformat()
    time_max = (now + timedelta(days=days)).isoformat()
    events_service = client.service.events()
    events_result = events_service.list(
        calendarId=client.calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
    ).execute()
    items = events_result.get("items", [])
    marked = filter_planz_events(items, force_legacy=force_legacy)
    print(f"Found {len(marked)} PLANZ events to delete (dry_run={dry_run})")
    for event in marked:
        summary = event.get("summary")
        event_id = event.get("id")
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        print(f"- {start} {event_id} {summary}")
        if not dry_run and event_id:
            events_service.delete(calendarId=client.calendar_id, eventId=event_id).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wipe PLANZ events from Google Calendar.")
    parser.add_argument("--days", type=int, default=120, help="Window in days before/after today to consider")
    parser.add_argument("--dry-run", action="store_true", help="Do not delete, only list")
    parser.add_argument("--force-legacy", action="store_true", help="Also delete legacy [PLZ] prefix events without tag")
    args = parser.parse_args()

    load_env()
    configure_logging()
    client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)
    wipe_planz_events(client, days=args.days, dry_run=args.dry_run, force_legacy=args.force_legacy)


if __name__ == "__main__":
    main()
