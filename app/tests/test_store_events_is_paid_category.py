"""Test that store_extracted_events writes is_paid + category to Event on create and update."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.models.event import Event
from app.db.models.source_url import SourceUrl
from app.services.extract.store_extracted_events import store_extracted_events


def _make_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


def _make_session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _make_source_url(session) -> SourceUrl:
    from app.db.models.source_domain import SourceDomain
    domain = SourceDomain(id=uuid.uuid4(), domain="example.com")
    session.add(domain)
    session.flush()
    su = SourceUrl(
        id=uuid.uuid4(),
        url="https://example.com/listing",
        domain_id=domain.id,
        content_hash="abc123",
        last_extracted_hash=None,
    )
    session.add(su)
    session.flush()
    return su


def _event_item(title: str = "Test Event", is_paid: bool = False, category: str | None = None) -> dict:
    return {
        "title": title,
        "start_time": "2030-06-15T10:00:00",
        "end_time": "2030-06-15T12:00:00",
        "location": "Munich",
        "description": "A test event",
        "source_url": "https://example.com/event",
        "detail_url": "https://example.com/event",
        "is_paid": is_paid,
        "category": category,
    }


def test_store_creates_event_with_is_paid() -> None:
    engine = _make_engine()
    session = _make_session(engine)
    source_url = _make_source_url(session)

    item = _event_item(is_paid=True, category="theater")
    now = datetime.now(tz=timezone.utc)
    store_extracted_events(session, source_url, [item], now)
    session.commit()

    event = session.scalar(select(Event))
    assert event is not None
    assert event.is_paid is True


def test_store_creates_event_with_category() -> None:
    engine = _make_engine()
    session = _make_session(engine)
    source_url = _make_source_url(session)

    item = _event_item(is_paid=False, category="museum")
    now = datetime.now(tz=timezone.utc)
    store_extracted_events(session, source_url, [item], now)
    session.commit()

    event = session.scalar(select(Event))
    assert event is not None
    assert event.category == "museum"


def test_store_updates_event_is_paid_and_category() -> None:
    engine = _make_engine()
    session = _make_session(engine)
    source_url = _make_source_url(session)

    # First extraction — no category or paid
    item = _event_item(is_paid=False, category=None)
    now = datetime.now(tz=timezone.utc)
    store_extracted_events(session, source_url, [item], now, force_extract=True)
    session.commit()

    event = session.scalar(select(Event))
    assert event.is_paid is False
    assert event.category is None

    # Second extraction — with category and paid
    source_url.last_extracted_hash = None
    item2 = _event_item(is_paid=True, category="workshop")
    store_extracted_events(session, source_url, [item2], now, force_extract=True)
    session.commit()

    session.expire_all()
    event = session.scalar(select(Event))
    assert event.is_paid is True
    assert event.category == "workshop"


def test_store_default_is_paid_false_when_missing() -> None:
    engine = _make_engine()
    session = _make_session(engine)
    source_url = _make_source_url(session)

    item = {
        "title": "Event Without Paid Flag",
        "start_time": "2030-07-01T10:00:00",
        "end_time": "2030-07-01T12:00:00",
        "source_url": "https://example.com/event2",
        "detail_url": "https://example.com/event2",
        # no is_paid, no category
    }
    now = datetime.now(tz=timezone.utc)
    store_extracted_events(session, source_url, [item], now)
    session.commit()

    event = session.scalar(select(Event))
    assert event is not None
    assert event.is_paid is False
    assert event.category is None
