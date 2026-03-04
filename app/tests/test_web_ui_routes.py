"""Tests for the web UI routes: status codes, redirects, auth flows."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.session import get_session
from app.main import create_app
from app.services.auth.auth_service import create_user, make_session_cookie


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _make_client(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    app = create_app()

    def override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    return TestClient(app, follow_redirects=False), SessionLocal


def test_landing_returns_200() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Munich Kids Events" in resp.content


def test_signup_get_returns_200() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.get("/signup")
    assert resp.status_code == 200


def test_login_get_returns_200() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.get("/login")
    assert resp.status_code == 200


def test_post_signup_redirects_to_setup() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.post("/signup", data={"email": "new@example.com", "password": "password123"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/setup"


def test_post_signup_duplicate_email_returns_422() -> None:
    engine = _make_engine()
    client, SessionLocal = _make_client(engine)
    session = SessionLocal()
    create_user(session, "dup@example.com", "pass")
    session.close()

    resp = client.post("/signup", data={"email": "dup@example.com", "password": "otherpass"})
    assert resp.status_code == 422
    assert b"already registered" in resp.content


def test_post_login_valid_redirects_to_settings() -> None:
    engine = _make_engine()
    client, SessionLocal = _make_client(engine)
    session = SessionLocal()
    create_user(session, "login@example.com", "mypassword")
    session.close()

    resp = client.post("/login", data={"email": "login@example.com", "password": "mypassword"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings"


def test_post_login_wrong_password_returns_401() -> None:
    engine = _make_engine()
    client, SessionLocal = _make_client(engine)
    session = SessionLocal()
    create_user(session, "wrong@example.com", "correctpass")
    session.close()

    resp = client.post("/login", data={"email": "wrong@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_unauthenticated_setup_redirects_to_login() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.get("/setup")
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]


def test_unauthenticated_settings_redirects_to_login() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.get("/settings")
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]


def test_unauthenticated_connect_redirects_to_login() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.get("/connect")
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]


def _auth_cookie(user_id: str) -> dict:
    return {"session_token": make_session_cookie(user_id)}


def test_authenticated_settings_returns_200() -> None:
    engine = _make_engine()
    client, SessionLocal = _make_client(engine)
    session = SessionLocal()
    user = create_user(session, "auth@example.com", "pass")
    user_id = str(user.id)
    session.close()

    resp = client.get("/settings", cookies=_auth_cookie(user_id))
    assert resp.status_code == 200


def test_post_settings_saves_prefs() -> None:
    engine = _make_engine()
    client, SessionLocal = _make_client(engine)
    session = SessionLocal()
    user = create_user(session, "prefs@example.com", "pass")
    user_id = str(user.id)
    session.close()

    resp = client.post(
        "/settings",
        data={"categories": ["theater", "museum"], "include_free": "1"},
        cookies=_auth_cookie(user_id),
    )
    assert resp.status_code == 200
    assert b"Preferences saved" in resp.content


def test_logout_clears_cookie() -> None:
    engine = _make_engine()
    client, _ = _make_client(engine)
    resp = client.post("/logout")
    assert resp.status_code == 303
    # Cookie should be deleted (set with empty value or max-age=0)
    assert "session_token" in resp.headers.get("set-cookie", "")
