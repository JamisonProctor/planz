"""Tests for user auth: hash/verify, create_user, authenticate, session cookies."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401
from app.services.auth.auth_service import (
    authenticate,
    create_user,
    hash_password,
    make_session_cookie,
    read_session_cookie,
    verify_password,
)


def _make_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


def _session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


# --- hash / verify ---

def test_hash_verify_round_trip() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_wrong_password() -> None:
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_hash_is_different_from_plaintext() -> None:
    hashed = hash_password("password123")
    assert hashed != "password123"


# --- create_user ---

def test_create_user_success() -> None:
    engine = _make_engine()
    session = _session(engine)
    user = create_user(session, "test@example.com", "password123")
    assert user.email == "test@example.com"
    assert user.id is not None


def test_create_user_auto_creates_feed_token() -> None:
    from app.db.models.feed_token import FeedToken
    from sqlalchemy import select

    engine = _make_engine()
    session = _session(engine)
    user = create_user(session, "user@example.com", "pass")
    token = session.scalar(select(FeedToken).where(FeedToken.user_id == user.id))
    assert token is not None
    assert len(token.token) > 0


def test_create_user_duplicate_email_raises() -> None:
    engine = _make_engine()
    session = _session(engine)
    create_user(session, "dup@example.com", "pass1")
    with pytest.raises(ValueError, match="already registered"):
        create_user(session, "dup@example.com", "pass2")


# --- authenticate ---

def test_authenticate_valid() -> None:
    engine = _make_engine()
    session = _session(engine)
    create_user(session, "auth@example.com", "correctpassword")
    user = authenticate(session, "auth@example.com", "correctpassword")
    assert user is not None
    assert user.email == "auth@example.com"


def test_authenticate_wrong_password() -> None:
    engine = _make_engine()
    session = _session(engine)
    create_user(session, "auth2@example.com", "correct")
    result = authenticate(session, "auth2@example.com", "wrong")
    assert result is None


def test_authenticate_unknown_email() -> None:
    engine = _make_engine()
    session = _session(engine)
    result = authenticate(session, "nobody@example.com", "password")
    assert result is None


# --- session cookie ---

def test_session_cookie_round_trip() -> None:
    cookie = make_session_cookie("some-user-id")
    user_id = read_session_cookie(cookie)
    assert user_id == "some-user-id"


def test_tampered_cookie_returns_none() -> None:
    cookie = make_session_cookie("user-123")
    tampered = cookie + "X"
    result = read_session_cookie(tampered)
    assert result is None


def test_garbage_cookie_returns_none() -> None:
    result = read_session_cookie("not-a-valid-cookie")
    assert result is None
