from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.services.calendar.sync_events import sync_unsynced_events


class _FakeCalendarClient:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.calls: list[str] = []

    def upsert_event(self, calendar_event):
        event_id = self._ids[len(self.calls)]
        self.calls.append(event_id)
        return event_id


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_sync_unsynced_events_creates_calendar_sync() -> None:
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
    count = sync_unsynced_events(session, client, now=now)

    rows = session.scalars(select(CalendarSync)).all()
    assert count == 2
    assert len(rows) == 2
    assert {row.calendar_event_id for row in rows} == {"abc123", "def456"}
    assert {row.event_id for row in rows} == {event1.id, event2.id}
    assert all(row.provider == "google" for row in rows)
    assert client.calls == ["abc123", "def456"]


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
    count = sync_unsynced_events(session, client, now=now)

    assert count == 1
    assert client.calls == ["newid"]


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
    count = sync_unsynced_events(session, client, now=now)

    assert count == 0
    assert client.calls == []
