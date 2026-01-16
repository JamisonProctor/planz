from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

WEEKEND_DAYS = {5, 6}


def derive_weekend_events(
    *,
    title: str,
    start_time: datetime,
    end_time: datetime,
    location: str | None,
    description: str | None,
    source_url: str,
) -> list[dict[str, Any]]:
    if end_time.date() <= start_time.date():
        return []

    tz = start_time.tzinfo or end_time.tzinfo
    is_all_day = start_time.time() == time(0, 0) and end_time.time() == time(0, 0)

    day = start_time.date()
    last_day = end_time.date()
    derived: list[dict[str, Any]] = []

    while day <= last_day:
        if day.weekday() in WEEKEND_DAYS:
            if is_all_day:
                day_start = datetime.combine(day, time(0, 0), tzinfo=tz)
                day_end = datetime.combine(day, time(23, 59), tzinfo=tz)
            else:
                day_start = datetime.combine(day, start_time.time(), tzinfo=tz)
                day_end = datetime.combine(day, end_time.time(), tzinfo=tz)

            suffix = "(Saturday)" if day.weekday() == 5 else "(Sunday)"
            derived.append(
                {
                    "title": f"{title} {suffix}",
                    "start_time": day_start,
                    "end_time": day_end,
                    "location": location,
                    "description": description,
                    "source_url": source_url,
                }
            )
        day += timedelta(days=1)

    return derived
