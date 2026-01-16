from __future__ import annotations

from datetime import datetime, timedelta
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.services.calendar.mapper import event_to_calendar_event

logger = logging.getLogger(__name__)

def sync_unsynced_events(
    session: Session,
    calendar_client,
    now: datetime,
    limit: int = 50,
    grace_hours: int = 0,
) -> dict[str, int]:
    grace_cutoff = now - timedelta(hours=grace_hours)
    skipped_already_synced = session.scalar(
        select(func.count(Event.id))
        .join(CalendarSync, CalendarSync.event_id == Event.id)
        .where(Event.start_time >= grace_cutoff)
    ) or 0
    skipped_too_old = session.scalar(
        select(func.count(Event.id))
        .outerjoin(CalendarSync, CalendarSync.event_id == Event.id)
        .where(CalendarSync.id.is_(None))
        .where(Event.start_time < grace_cutoff)
    ) or 0

    stmt = (
        select(Event)
        .outerjoin(CalendarSync, CalendarSync.event_id == Event.id)
        .where(CalendarSync.id.is_(None))
        .where(Event.start_time >= grace_cutoff)
        .order_by(Event.start_time)
        .limit(limit)
    )
    events = session.scalars(stmt).all()

    synced = 0
    for event in events:
        calendar_event = event_to_calendar_event(event)
        try:
            calendar_event_id = calendar_client.upsert_event(calendar_event)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to sync event id=%s: %s", event.id, exc, exc_info=True)
            continue

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
    return {
        "synced_count": synced,
        "skipped_already_synced": skipped_already_synced,
        "skipped_too_old": skipped_too_old,
    }
