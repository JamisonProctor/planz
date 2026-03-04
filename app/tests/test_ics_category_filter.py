"""Test ICS category and paid filters, including convenience routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.models.event import Event
from app.db.session import get_session
from app.main import create_app


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _make_event(
    title: str,
    category: str | None = None,
    is_paid: bool = False,
    days_ahead: int = 5,
) -> Event:
    now = datetime.now(tz=timezone.utc)
    start = now + timedelta(days=days_ahead)
    end = start + timedelta(hours=2)
    return Event(
        id=uuid.uuid4(),
        title=title,
        start_time=start,
        end_time=end,
        is_calendar_candidate=True,
        category=category,
        is_paid=is_paid,
    )


@pytest.fixture
def client_with_events():
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    session = SessionLocal()
    session.add(_make_event("Theater Show", category="theater", is_paid=True))
    session.add(_make_event("Museum Visit", category="museum", is_paid=False))
    session.add(_make_event("Free Workshop", category="workshop", is_paid=False))
    session.add(_make_event("Outdoor Hike", category="outdoor", is_paid=False))
    session.commit()
    session.close()

    app = create_app()

    def override_session():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_all_events_feed(client_with_events) -> None:
    resp = client_with_events.get("/events.ics")
    assert resp.status_code == 200
    assert b"BEGIN:VCALENDAR" in resp.content
    assert b"Theater Show" in resp.content
    assert b"Museum Visit" in resp.content


def test_category_filter_theater(client_with_events) -> None:
    resp = client_with_events.get("/events.ics?category=theater")
    assert resp.status_code == 200
    assert b"Theater Show" in resp.content
    assert b"Museum Visit" not in resp.content


def test_category_filter_museum(client_with_events) -> None:
    resp = client_with_events.get("/events.ics?category=museum")
    assert resp.status_code == 200
    assert b"Museum Visit" in resp.content
    assert b"Theater Show" not in resp.content


def test_paid_filter_true(client_with_events) -> None:
    resp = client_with_events.get("/events.ics?paid=true")
    assert resp.status_code == 200
    assert b"Theater Show" in resp.content
    assert b"Museum Visit" not in resp.content


def test_paid_filter_false(client_with_events) -> None:
    resp = client_with_events.get("/events.ics?paid=false")
    assert resp.status_code == 200
    assert b"Museum Visit" in resp.content
    assert b"Theater Show" not in resp.content


def test_invalid_category_returns_400(client_with_events) -> None:
    resp = client_with_events.get("/events.ics?category=invalid")
    assert resp.status_code == 400


def test_convenience_route_free(client_with_events) -> None:
    resp = client_with_events.get("/events/free.ics")
    assert resp.status_code == 200
    assert b"Museum Visit" in resp.content
    assert b"Theater Show" not in resp.content


def test_convenience_route_paid(client_with_events) -> None:
    resp = client_with_events.get("/events/paid.ics")
    assert resp.status_code == 200
    assert b"Theater Show" in resp.content
    assert b"Museum Visit" not in resp.content


def test_convenience_route_theater(client_with_events) -> None:
    resp = client_with_events.get("/events/theater.ics")
    assert resp.status_code == 200
    assert b"Theater Show" in resp.content
    assert b"Museum Visit" not in resp.content


def test_convenience_route_museum(client_with_events) -> None:
    resp = client_with_events.get("/events/museum.ics")
    assert resp.status_code == 200
    assert b"Museum Visit" in resp.content
    assert b"Theater Show" not in resp.content


def test_convenience_route_workshop(client_with_events) -> None:
    resp = client_with_events.get("/events/workshop.ics")
    assert resp.status_code == 200
    assert b"Free Workshop" in resp.content
    assert b"Theater Show" not in resp.content


def test_convenience_route_outdoor(client_with_events) -> None:
    resp = client_with_events.get("/events/outdoor.ics")
    assert resp.status_code == 200
    assert b"Outdoor Hike" in resp.content
    assert b"Theater Show" not in resp.content


def test_cal_name_category(client_with_events) -> None:
    resp = client_with_events.get("/events.ics?category=theater")
    assert b"Munich Kids Events" in resp.content
    assert b"Theater" in resp.content


def test_cal_name_free(client_with_events) -> None:
    resp = client_with_events.get("/events/free.ics")
    assert b"Free" in resp.content
