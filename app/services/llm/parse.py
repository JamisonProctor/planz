from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

REQUIRED_FIELDS = [
    "title",
    "start_time",
    "end_time",
    "location",
    "description",
    "source_url",
]


def parse_kids_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tz = ZoneInfo("Europe/Berlin")
    cleaned: list[dict[str, Any]] = []

    for item in raw_events:
        if not isinstance(item, dict):
            continue

        if any(field not in item for field in REQUIRED_FIELDS):
            continue

        title = _as_str(item.get("title"))
        location = _as_str(item.get("location"))
        description = _as_str(item.get("description"))
        source_url = _as_str(item.get("source_url"))
        if not all([title, location, description, source_url]):
            continue

        start_time = _parse_datetime(item.get("start_time"), tz)
        end_time = _parse_datetime(item.get("end_time"), tz)
        if not start_time or not end_time:
            continue
        if end_time <= start_time:
            continue

        cleaned.append(
            {
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "description": description,
                "source_url": source_url,
            }
        )

    return cleaned


def _as_str(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _parse_datetime(value: Any, tz: ZoneInfo) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)

    return parsed
