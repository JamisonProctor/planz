from __future__ import annotations

from uuid import UUID

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_session
from app.services.auth.auth_service import read_session_cookie


def get_optional_user(
    session_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> User | None:
    if session_token is None:
        return None
    user_id_str = read_session_cookie(session_token)
    if user_id_str is None:
        return None
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        return None
    return session.scalar(select(User).where(User.id == user_id))


def get_current_user(
    session_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> User:
    user = get_optional_user(session_token=session_token, session=session)
    if user is None:
        raise HTTPException(status_code=307, detail="Not authenticated", headers={"Location": "/login"})
    return user
