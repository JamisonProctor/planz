"""Tests for the personalized feed endpoint GET /feed/{token}/events.ics."""
from __future__ import annotations

import json
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
from app.db.models.feed_token import FeedToken
from app.db.models.user import User
from app.db.models.user_preference import UserPreference
from app.db.session import get_session
from app.main import create_app
from app.services.auth.auth_service import hash_password


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
    session,
    title: str,
    is_paid: bool = False,
    category: str | None = None,
    days_ahead: int = 5,
):
    now = datetime.now(tz=timezone.utc)
    start = now + timedelta(days=days_ahead)
    end = start + timedelta(hours=2)
    e = Event(
        id=uuid.uuid4(),
        title=title,
        start_time=start,
        end_time=end,
        is_calendar_candidate=True,
        is_paid=is_paid,
        category=category,
    )
    session.add(e)
    return e


def _make_user_with_token(session, pref_kwargs=None) -> tuple[User, str]:
    user = User(id=uuid.uuid4(), email="test@example.com", password_hash=hash_password("pass"))
    session.add(user)
    session.flush()

    token_str = "test-token-abc123"
    ft = FeedToken(id=uuid.uuid4(), user_id=user.id, token=token_str)
    session.add(ft)

    pref_defaults = {
        "include_paid": True,
        "include_free": True,
        "selected_categories": None,
    }
    pref_defaults.update(pref_kwargs or {})
    pref = UserPreference(id=uuid.uuid4(), user_id=user.id, **pref_defaults)
    session.add(pref)
    session.commit()
    return user, token_str


@pytest.fixture
def client_with_data():
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    session = SessionLocal()
    _make_event(session, "Theater Show", is_paid=True, category="theater")
    _make_event(session, "Free Museum", is_paid=False, category="museum")
    _make_event(session, "Workshop Fun", is_paid=False, category="workshop")
    _, token = _make_user_with_token(session)
    session.close()

    app = create_app()

    def override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    return TestClient(app), token


def test_valid_token_returns_ics(client_with_data) -> None:
    client, token = client_with_data
    resp = client.get(f"/feed/{token}/events.ics")
    assert resp.status_code == 200
    assert b"BEGIN:VCALENDAR" in resp.content
    assert b"Theater Show" in resp.content


def test_unknown_token_returns_404() -> None:
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    app = create_app()

    def override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    resp = client.get("/feed/nonexistent-token/events.ics")
    assert resp.status_code == 404


def test_include_paid_false_excludes_paid() -> None:
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    session = SessionLocal()
    _make_event(session, "Paid Theater", is_paid=True, category="theater")
    _make_event(session, "Free Museum", is_paid=False, category="museum")
    _, token = _make_user_with_token(session, pref_kwargs={"include_paid": False, "include_free": True})
    session.close()

    app = create_app()

    def override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    resp = client.get(f"/feed/{token}/events.ics")
    assert resp.status_code == 200
    assert b"Paid Theater" not in resp.content
    assert b"Free Museum" in resp.content


def test_selected_categories_filters_events() -> None:
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    session = SessionLocal()
    _make_event(session, "Theater Show", category="theater")
    _make_event(session, "Museum Visit", category="museum")
    _make_event(session, "Workshop", category="workshop")
    _, token = _make_user_with_token(session, pref_kwargs={
        "selected_categories": json.dumps(["theater"]),
    })
    session.close()

    app = create_app()

    def override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    resp = client.get(f"/feed/{token}/events.ics")
    assert resp.status_code == 200
    assert b"Theater Show" in resp.content
    assert b"Museum Visit" not in resp.content
    assert b"Workshop" not in resp.content
