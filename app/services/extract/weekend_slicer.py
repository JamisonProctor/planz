from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

WEEKEND_DAYS = {5, 6}


def derive_daily_events(
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
        if is_all_day:
            day_start = datetime.combine(day, time(0, 0), tzinfo=tz)
            day_end = datetime.combine(day, time(23, 59), tzinfo=tz)
        else:
            day_start = datetime.combine(day, start_time.time(), tzinfo=tz)
            day_end = datetime.combine(day, end_time.time(), tzinfo=tz)

        derived.append(
            {
                "title": title,
                "start_time": day_start,
                "end_time": day_end,
                "location": location,
                "description": description,
                "source_url": source_url,
                "is_calendar_candidate": _is_recommendation_day(day),
            }
        )
        day += timedelta(days=1)

    return derived


def _is_recommendation_day(day: date) -> bool:
    if day.weekday() in WEEKEND_DAYS:
        return True
    return day in _bavaria_public_holidays(day.year)


def _bavaria_public_holidays(year: int) -> set[date]:
    easter_sunday = _easter_sunday(year)
    return {
        date(year, 1, 1),   # New Year
        date(year, 1, 6),   # Epiphany
        easter_sunday - timedelta(days=2),   # Good Friday
        easter_sunday + timedelta(days=1),   # Easter Monday
        date(year, 5, 1),   # Labour Day
        easter_sunday + timedelta(days=39),  # Ascension Day
        easter_sunday + timedelta(days=50),  # Whit Monday
        easter_sunday + timedelta(days=60),  # Corpus Christi
        date(year, 8, 15),  # Assumption Day (Munich)
        date(year, 10, 3),  # German Unity Day
        date(year, 11, 1),  # All Saints' Day
        date(year, 12, 25), # Christmas Day
        date(year, 12, 26), # Second Christmas Day
    }


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
