from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.feed_token import FeedToken
from app.db.models.user import User
from app.db.models.user_preference import UserPreference
from app.db.session import get_session
from app.domain.constants import EVENT_CATEGORIES
from app.services.auth.auth_service import (
    authenticate,
    create_user,
    make_session_cookie,
    read_session_cookie,
)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()

_CATEGORY_ICONS = {
    "theater": "🎭",
    "museum": "🏛️",
    "workshop": "🔧",
    "outdoor": "🌳",
    "sport": "⚽",
    "concert": "🎵",
    "other": "✨",
}

_CATEGORIES_WITH_ICONS = [(cat, _CATEGORY_ICONS.get(cat, "•")) for cat in EVENT_CATEGORIES]


def _get_user(session_token: str | None, session: Session) -> User | None:
    if not session_token:
        return None
    user_id_str = read_session_cookie(session_token)
    if not user_id_str:
        return None
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        return None
    return session.scalar(select(User).where(User.id == user_id))


def _get_token(user: User, session: Session) -> str | None:
    ft = session.scalar(select(FeedToken).where(FeedToken.user_id == user.id))
    return ft.token if ft else None


def _get_pref(user: User, session: Session) -> UserPreference | None:
    return session.scalar(select(UserPreference).where(UserPreference.user_id == user.id))


def _selected_categories(pref: UserPreference | None) -> list[str]:
    if pref is None or pref.selected_categories is None:
        return list(EVENT_CATEGORIES)
    try:
        cats = json.loads(pref.selected_categories)
        return cats if isinstance(cats, list) else list(EVENT_CATEGORIES)
    except (json.JSONDecodeError, TypeError):
        return list(EVENT_CATEGORIES)


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, session_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    user = _get_user(session_token, session)
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "user": user,
        "categories": _CATEGORIES_WITH_ICONS,
    })


@router.get("/signup", response_class=HTMLResponse)
def signup_get(request: Request, session_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    user = _get_user(session_token, session)
    if user:
        return RedirectResponse("/settings", status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request, "user": None, "error": None, "email": None})


@router.post("/signup")
def signup_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        user = create_user(session, email.strip().lower(), password)
    except ValueError as exc:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "user": None,
            "error": str(exc),
            "email": email,
        }, status_code=422)

    cookie = make_session_cookie(str(user.id))
    response = RedirectResponse("/setup", status_code=303)
    response.set_cookie("session_token", cookie, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request, session_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    user = _get_user(session_token, session)
    if user:
        return RedirectResponse("/settings", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": None, "email": None})


@router.post("/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = authenticate(session, email.strip().lower(), password)
    if user is None:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None,
            "error": "Invalid email or password.",
            "email": email,
        }, status_code=401)

    cookie = make_session_cookie(str(user.id))
    response = RedirectResponse("/settings", status_code=303)
    response.set_cookie("session_token", cookie, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session_token")
    return response


@router.get("/setup", response_class=HTMLResponse)
def setup_get(request: Request, session_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    user = _get_user(session_token, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    pref = _get_pref(user, session)
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "user": user,
        "categories": _CATEGORIES_WITH_ICONS,
        "selected_categories": _selected_categories(pref),
        "include_paid": pref.include_paid if pref else True,
        "include_free": pref.include_free if pref else True,
        "error": None,
        "success": None,
    })


@router.post("/setup")
def setup_post(
    request: Request,
    categories: list[str] = Form(default=[]),
    include_paid: str | None = Form(default=None),
    include_free: str | None = Form(default=None),
    session_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    user = _get_user(session_token, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    valid_cats = [c for c in categories if c in EVENT_CATEGORIES]
    pref = _get_pref(user, session)
    if pref is None:
        pref = UserPreference(user_id=user.id)
        session.add(pref)

    pref.selected_categories = json.dumps(valid_cats) if valid_cats else None
    pref.include_paid = include_paid == "1"
    pref.include_free = include_free == "1"
    session.commit()

    return RedirectResponse("/connect", status_code=303)


@router.get("/connect", response_class=HTMLResponse)
def connect_get(request: Request, session_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    user = _get_user(session_token, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    token = _get_token(user, session)
    host = request.headers.get("host", "localhost:8000")
    return templates.TemplateResponse("connect.html", {
        "request": request,
        "user": user,
        "token": token,
        "host": host,
    })


@router.get("/settings", response_class=HTMLResponse)
def settings_get(request: Request, session_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    user = _get_user(session_token, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    pref = _get_pref(user, session)
    token = _get_token(user, session)
    host = request.headers.get("host", "localhost:8000")
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "categories": _CATEGORIES_WITH_ICONS,
        "selected_categories": _selected_categories(pref),
        "include_paid": pref.include_paid if pref else True,
        "include_free": pref.include_free if pref else True,
        "token": token,
        "host": host,
        "error": None,
        "success": None,
    })


@router.post("/settings")
def settings_post(
    request: Request,
    categories: list[str] = Form(default=[]),
    include_paid: str | None = Form(default=None),
    include_free: str | None = Form(default=None),
    session_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    user = _get_user(session_token, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    valid_cats = [c for c in categories if c in EVENT_CATEGORIES]
    pref = _get_pref(user, session)
    if pref is None:
        pref = UserPreference(user_id=user.id)
        session.add(pref)

    pref.selected_categories = json.dumps(valid_cats) if valid_cats else None
    pref.include_paid = include_paid == "1"
    pref.include_free = include_free == "1"
    session.commit()

    token = _get_token(user, session)
    host = request.headers.get("host", "localhost:8000")
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "categories": _CATEGORIES_WITH_ICONS,
        "selected_categories": _selected_categories(pref),
        "include_paid": pref.include_paid,
        "include_free": pref.include_free,
        "token": token,
        "host": host,
        "error": None,
        "success": "Preferences saved.",
    })
