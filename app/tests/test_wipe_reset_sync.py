from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.scripts.calendar_wipe_planz import reset_sync_state


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _make_event(session, google_event_id: str | None = "gcal-123") -> Event:
    now = datetime.now(tz=timezone.utc)
    event = Event(
        title="Test Event",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
        google_event_id=google_event_id,
        is_calendar_candidate=True,
    )
    session.add(event)
    session.flush()
    sync = CalendarSync(
        event_id=event.id,
        provider="google",
        calendar_event_id=google_event_id,
        synced_at=now,
    )
    session.add(sync)
    session.commit()
    return event


def test_reset_sync_state_clears_calendar_syncs() -> None:
    session = _make_session()
    _make_event(session)
    assert session.scalar(select(CalendarSync)) is not None

    reset_sync_state(session)

    assert session.scalar(select(CalendarSync)) is None


def test_reset_sync_state_clears_google_event_id() -> None:
    session = _make_session()
    event = _make_event(session)
    assert event.google_event_id is not None

    reset_sync_state(session)

    session.refresh(event)
    assert event.google_event_id is None


def test_reset_sync_state_allows_resync() -> None:
    """After reset, the sync query should find the event as unsynced."""
    from sqlalchemy import func
    session = _make_session()
    _make_event(session)

    reset_sync_state(session)

    unsynced_count = session.scalar(
        select(func.count(Event.id))
        .outerjoin(CalendarSync, CalendarSync.event_id == Event.id)
        .where(CalendarSync.id.is_(None))
    )
    assert unsynced_count == 1
