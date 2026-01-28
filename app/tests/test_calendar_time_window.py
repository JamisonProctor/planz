from datetime import datetime, timedelta, timezone

import logging

from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.google_calendar_service import (
    GoogleCalendarClient,
    _build_time_window,
)


def test_build_time_window_timed_event_has_positive_range() -> None:
    start = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    end = start
    cal = CalendarEvent(title="t", start=start, end=end)
    time_min, time_max = _build_time_window(cal)
    assert time_min and time_max
    assert datetime.fromisoformat(time_max) > datetime.fromisoformat(time_min)


def test_build_time_window_all_day_spans_day() -> None:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    cal = CalendarEvent(title="all", start=start, end=end)
    time_min, time_max = _build_time_window(cal)
    assert time_min and time_max
    assert datetime.fromisoformat(time_max) - datetime.fromisoformat(time_min) >= timedelta(days=1)


class _DummyEvents:
    def __init__(self) -> None:
        self.list_called = False

    def list(self, **kwargs):
        self.list_called = True
        return self

    def execute(self):
        return {"items": []}


class _DummyService:
    def __init__(self, events_obj) -> None:
        self._events = events_obj

    def events(self):
        return self._events


def test_find_event_skips_when_window_invalid(monkeypatch, caplog) -> None:
    events_obj = _DummyEvents()
    client = GoogleCalendarClient(calendar_id="cid", service=_DummyService(events_obj), allow_in_tests=True)

    monkeypatch.setattr("app.services.calendar.google_calendar_service._build_time_window", lambda *args, **kwargs: (None, None))
    caplog.set_level(logging.ERROR)

    result = client.find_event_by_key("key123", None)
    assert result is None
    assert events_obj.list_called is False
    assert any("invalid time window" in rec.message for rec in caplog.records)
