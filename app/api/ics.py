from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.event import Event
from app.db.session import get_session
from app.services.ics.ics_service import build_ics

router = APIRouter()


@router.get("/events.ics")
def get_ics_feed(
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    if settings.ICS_FEED_TOKEN and token != settings.ICS_FEED_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")

    now = datetime.now(tz=timezone.utc)
    events = session.scalars(
        select(Event)
        .where(Event.is_calendar_candidate == True)  # noqa: E712
        .where(Event.end_time >= now)
        .order_by(Event.start_time.asc())
    ).all()

    content = build_ics(list(events))
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="munich-kids.ics"'},
    )
