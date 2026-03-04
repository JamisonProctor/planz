from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event as VEvent, vText

from app.db.models.event import Event

BERLIN = ZoneInfo("Europe/Berlin")


def build_ics(events: list[Event], cal_name: str = "Munich Kids Events") -> bytes:
    cal = Calendar()
    cal.add("PRODID", "-//PLANZ//planz//EN")
    cal.add("VERSION", "2.0")
    cal.add("X-WR-CALNAME", cal_name)
    cal.add("REFRESH-INTERVAL;VALUE=DURATION", "PT6H")
    cal.add("METHOD", "PUBLISH")

    now_utc = datetime.now(tz=timezone.utc)

    for event in events:
        vevent = VEvent()

        uid_source = event.external_key or str(event.id)
        uid = hashlib.sha256(uid_source.encode()).hexdigest()[:16] + "@planz"
        vevent.add("UID", uid)

        vevent.add("SUMMARY", event.title)

        start = _ensure_berlin(event.start_time)
        end = _ensure_berlin(event.end_time)
        vevent.add("DTSTART", start)
        vevent.add("DTEND", end)

        if event.location:
            vevent.add("LOCATION", event.location)

        description = event.description or ""
        if event.source_url:
            if description:
                description += "\n\nMore info: " + event.source_url
            else:
                description = "More info: " + event.source_url
        if description:
            vevent.add("DESCRIPTION", description)

        if event.source_url:
            vevent.add("URL", event.source_url)

        vevent.add("TRANSP", "OPAQUE")
        vevent.add("DTSTAMP", now_utc)

        cal.add_component(vevent)

    return cal.to_ical()


def _ensure_berlin(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BERLIN)
    return dt.astimezone(BERLIN)
