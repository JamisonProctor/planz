from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.services.calendar.mapper import event_to_calendar_event


def sync_unsynced_events(
    session: Session,
    calendar_client,
    now: datetime,
    limit: int = 50,
) -> int:
    stmt = (
        select(Event)
        .outerjoin(CalendarSync, CalendarSync.event_id == Event.id)
        .where(CalendarSync.id.is_(None))
        .where(Event.start_time >= now)
        .order_by(Event.start_time)
        .limit(limit)
    )
    events = session.scalars(stmt).all()

    synced = 0
    for event in events:
        calendar_event = event_to_calendar_event(event)
        calendar_event_id = calendar_client.upsert_event(calendar_event)
        session.add(
            CalendarSync(
                event_id=event.id,
                provider="google",
                calendar_event_id=calendar_event_id,
                synced_at=now,
            )
        )
        synced += 1

    session.commit()
    return synced
