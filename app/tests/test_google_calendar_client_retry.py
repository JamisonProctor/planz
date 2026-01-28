from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.google_calendar_service import GoogleCalendarClient


def _make_rate_limit_error() -> HttpError:
    resp = SimpleNamespace(status=403, reason="rateLimitExceeded")
    content = json.dumps(
        {
            "error": {
                "errors": [
                    {
                        "reason": "rateLimitExceeded",
                        "message": "Rate Limit Exceeded",
                    }
                ]
            }
        }
    ).encode()
    return HttpError(resp, content, uri="")


class _DummyEvents:
    def __init__(self, failures: int) -> None:
        self.calls = 0
        self.failures = failures

    def insert(self, calendarId, body):  # noqa: N802
        return self

    def update(self, calendarId, eventId, body):  # noqa: N802
        return self

    def execute(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise _make_rate_limit_error()
        return {"id": f"evt-{self.calls}"}


class _DummyService:
    def __init__(self, events_obj: _DummyEvents) -> None:
        self._events = events_obj

    def events(self):  # noqa: D401
        return self._events


def test_upsert_retries_on_rate_limit(monkeypatch) -> None:
    events_obj = _DummyEvents(failures=2)
    client = GoogleCalendarClient(
        calendar_id="cid",
        service=_DummyService(events_obj),
        allow_in_tests=True,
    )

    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    cal_event = CalendarEvent(
        title="Test",
        start=datetime.now(tz=timezone.utc),
        end=datetime.now(tz=timezone.utc) + timedelta(hours=1),
    )

    result = client.upsert_event(cal_event)

    assert result == "evt-3"
    assert events_obj.calls == 3
    assert len(sleeps) == 2
