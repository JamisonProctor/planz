from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.event import Event
from app.db.models.feed_token import FeedToken
from app.db.models.user_preference import UserPreference
from app.db.session import get_session
from app.services.ics.ics_service import build_ics

router = APIRouter()


@router.get("/feed/{token}/events.ics")
def get_personalized_feed(token: str, session: Session = Depends(get_session)) -> Response:
    feed_token = session.scalar(select(FeedToken).where(FeedToken.token == token))
    if feed_token is None:
        raise HTTPException(status_code=404, detail="Feed not found")

    pref = session.scalar(
        select(UserPreference).where(UserPreference.user_id == feed_token.user_id)
    )

    now = datetime.now(tz=timezone.utc)
    stmt = (
        select(Event)
        .where(Event.is_calendar_candidate == True)  # noqa: E712
        .where(Event.end_time >= now)
    )

    if pref is not None:
        if pref.selected_categories is not None:
            try:
                cats = json.loads(pref.selected_categories)
                if cats:
                    stmt = stmt.where(Event.category.in_(cats))
            except (json.JSONDecodeError, TypeError):
                pass

        if pref.include_paid and not pref.include_free:
            stmt = stmt.where(Event.is_paid == True)  # noqa: E712
        elif pref.include_free and not pref.include_paid:
            stmt = stmt.where(Event.is_paid == False)  # noqa: E712
        # if both true or both false: no paid filter (both = no filter, neither = empty result handled by returning all)

    stmt = stmt.order_by(Event.start_time.asc())
    events = session.scalars(stmt).all()

    content = build_ics(list(events), cal_name="My Munich Kids Events")
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="my-munich-kids.ics"'},
    )
