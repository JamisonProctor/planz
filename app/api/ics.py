from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.event import Event
from app.db.session import get_session
from app.domain.constants import EVENT_CATEGORIES
from app.services.ics.ics_service import build_ics

router = APIRouter()

_CATEGORY_LABELS = {
    "theater": "Theater",
    "museum": "Museum",
    "workshop": "Workshop",
    "outdoor": "Outdoor",
    "sport": "Sport",
    "concert": "Concert",
    "other": "Other",
}


def _get_ics_feed(
    session: Session,
    token: str | None = None,
    category: str | None = None,
    paid: str | None = None,
) -> Response:
    if settings.ICS_FEED_TOKEN and token != settings.ICS_FEED_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")

    if category is not None and category not in EVENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    now = datetime.now(tz=timezone.utc)
    stmt = (
        select(Event)
        .where(Event.is_calendar_candidate == True)  # noqa: E712
        .where(Event.end_time >= now)
    )

    if category is not None:
        stmt = stmt.where(Event.category == category)
    if paid == "true":
        stmt = stmt.where(Event.is_paid == True)  # noqa: E712
    elif paid == "false":
        stmt = stmt.where(Event.is_paid == False)  # noqa: E712

    stmt = stmt.order_by(Event.start_time.asc())
    events = session.scalars(stmt).all()

    if category is not None:
        label = _CATEGORY_LABELS.get(category, category.capitalize())
        cal_name = f"Munich Kids Events — {label}"
    elif paid == "true":
        cal_name = "Munich Kids Events — Paid"
    elif paid == "false":
        cal_name = "Munich Kids Events — Free"
    else:
        cal_name = "Munich Kids Events"

    content = build_ics(list(events), cal_name=cal_name)
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="munich-kids.ics"'},
    )


@router.get("/events.ics")
def get_ics_feed(
    token: str | None = Query(default=None),
    category: str | None = Query(default=None),
    paid: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category=category, paid=paid)


@router.get("/events/free.ics")
def get_free_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, paid="false")


@router.get("/events/paid.ics")
def get_paid_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, paid="true")


@router.get("/events/theater.ics")
def get_theater_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category="theater")


@router.get("/events/museum.ics")
def get_museum_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category="museum")


@router.get("/events/workshop.ics")
def get_workshop_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category="workshop")


@router.get("/events/outdoor.ics")
def get_outdoor_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category="outdoor")


@router.get("/events/sport.ics")
def get_sport_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category="sport")


@router.get("/events/concert.ics")
def get_concert_ics(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    return _get_ics_feed(session=session, token=token, category="concert")
