from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from icalendar import Calendar

from app.services.ics.ics_service import build_ics


def _make_event(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id=uuid.uuid4(),
        title="Test Event",
        start_time=datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        location="Marienplatz, Munich",
        description="A fun event for kids.",
        source_url="https://example.com/event",
        external_key="test-external-key-123",
        is_calendar_candidate=True,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_build_ics_returns_bytes():
    result = build_ics([_make_event()])
    assert isinstance(result, bytes)
    assert result.startswith(b"BEGIN:VCALENDAR")


def test_build_ics_event_fields():
    event = _make_event()
    result = build_ics([event])
    cal = Calendar.from_ical(result)

    vevents = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(vevents) == 1
    ve = vevents[0]

    assert str(ve["SUMMARY"]) == "Test Event"
    assert "Marienplatz" in str(ve["LOCATION"])
    assert ve["DTSTART"].dt is not None
    assert ve["DTEND"].dt is not None
    assert "@planz" in str(ve["UID"])


def test_build_ics_stable_uid():
    event = _make_event(external_key="stable-key-abc")
    uid_first = _extract_uid(build_ics([event]))
    uid_second = _extract_uid(build_ics([event]))
    assert uid_first == uid_second


def test_build_ics_empty_events():
    result = build_ics([])
    assert isinstance(result, bytes)
    assert b"BEGIN:VCALENDAR" in result
    assert b"BEGIN:VEVENT" not in result


def test_build_ics_description_includes_source_url():
    event = _make_event(
        description="A wonderful show.",
        source_url="https://example.com/show",
    )
    result = build_ics([event])
    cal = Calendar.from_ical(result)
    vevents = [c for c in cal.walk() if c.name == "VEVENT"]
    desc = str(vevents[0]["DESCRIPTION"])
    assert "A wonderful show." in desc
    assert "https://example.com/show" in desc


def _extract_uid(ics_bytes: bytes) -> str:
    cal = Calendar.from_ical(ics_bytes)
    for component in cal.walk():
        if component.name == "VEVENT":
            return str(component["UID"])
    raise AssertionError("No VEVENT found")
