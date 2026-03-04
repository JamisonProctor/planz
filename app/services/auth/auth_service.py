from __future__ import annotations

import secrets

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.feed_token import FeedToken
from app.db.models.user import User
from app.db.models.user_preference import UserPreference

_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days in seconds


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_user(session: Session, email: str, password: str) -> User:
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ValueError(f"Email already registered: {email}")

    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    session.flush()

    token = FeedToken(user_id=user.id, token=secrets.token_hex(32))
    session.add(token)

    pref = UserPreference(
        user_id=user.id,
        selected_categories=None,
        include_paid=True,
        include_free=True,
    )
    session.add(pref)
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def make_session_cookie(user_id: str) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(str(user_id), salt="session")


def read_session_cookie(cookie: str) -> str | None:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return s.loads(cookie, salt="session", max_age=_COOKIE_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
