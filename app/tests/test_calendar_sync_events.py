from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.services.calendar.sync_events import sync_unsynced_events


class _FakeCalendarClient:
    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = responses
        self.calls: int = 0

    def upsert_event(self, calendar_event):
        response = self._responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_sync_unsynced_events_creates_calendar_sync_rows() -> None:
    session = _make_session()
    now = datetime.now(tz=timezone.utc)

    event1 = Event(
        title="Event 1",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
    )
    event2 = Event(
        title="Event 2",
        start_time=now + timedelta(days=2),
        end_time=now + timedelta(days=2, hours=1),
    )
    session.add_all([event1, event2])
    session.commit()

    client = _FakeCalendarClient(["abc123", "def456"])
    stats = sync_unsynced_events(session, client, now=now, grace_hours=12)

    rows = session.scalars(select(CalendarSync)).all()
    assert stats["synced_count"] == 2
    assert len(rows) == 2
    assert {row.calendar_event_id for row in rows} == {"abc123", "def456"}
    assert {row.event_id for row in rows} == {event1.id, event2.id}
    assert all(row.provider == "google" for row in rows)
    assert client.calls == 2
    for row in rows:
        assert row.synced_at.replace(tzinfo=timezone.utc) == now


def test_sync_unsynced_events_skips_already_synced() -> None:
    session = _make_session()
    now = datetime.now(tz=timezone.utc)

    synced_event = Event(
        title="Synced",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
    )
    unsynced_event = Event(
        title="Unsynced",
        start_time=now + timedelta(days=2),
        end_time=now + timedelta(days=2, hours=1),
    )
    session.add_all([synced_event, unsynced_event])
    session.commit()

    session.add(
        CalendarSync(
            event_id=synced_event.id,
            provider="google",
            calendar_event_id="already",
            synced_at=now,
        )
    )
    session.commit()

    client = _FakeCalendarClient(["newid"])
    stats = sync_unsynced_events(session, client, now=now, grace_hours=12)

    assert stats["synced_count"] == 1
    assert client.calls == 1


def test_sync_unsynced_events_skips_past_events() -> None:
    session = _make_session()
    now = datetime.now(tz=timezone.utc)

    past_event = Event(
        title="Past",
        start_time=now - timedelta(days=1),
        end_time=now - timedelta(days=1, hours=-1),
    )
    session.add(past_event)
    session.commit()

    client = _FakeCalendarClient(["ignored"])
    stats = sync_unsynced_events(session, client, now=now, grace_hours=12)

    assert stats["synced_count"] == 0
    assert client.calls == 0


def test_sync_unsynced_events_continues_on_failure() -> None:
    session = _make_session()
    now = datetime.now(tz=timezone.utc)

    event1 = Event(
        title="Event 1",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
    )
    event2 = Event(
        title="Event 2",
        start_time=now + timedelta(days=2),
        end_time=now + timedelta(days=2, hours=1),
    )
    session.add_all([event1, event2])
    session.commit()

    client = _FakeCalendarClient([RuntimeError("boom"), "ok-id"])
    stats = sync_unsynced_events(session, client, now=now, grace_hours=12)

    rows = session.scalars(select(CalendarSync)).all()
    assert stats["synced_count"] == 1
    assert len(rows) == 1
    assert rows[0].calendar_event_id == "ok-id"
    assert client.calls == 2


def test_sync_unsynced_events_respects_grace_window() -> None:
    session = _make_session()
    now = datetime.now(tz=timezone.utc)

    recent_past = Event(
        title="Recent Past",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
    )
    too_old = Event(
        title="Too Old",
        start_time=now - timedelta(hours=30),
        end_time=now - timedelta(hours=29),
    )
    session.add_all([recent_past, too_old])
    session.commit()

    client = _FakeCalendarClient(["ok-id"])
    stats = sync_unsynced_events(session, client, now=now, grace_hours=12)

    rows = session.scalars(select(CalendarSync)).all()
    assert stats["synced_count"] == 1
    assert stats["skipped_too_old"] == 1
    assert len(rows) == 1
    assert rows[0].event_id == recent_past.id
