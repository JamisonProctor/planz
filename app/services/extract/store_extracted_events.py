from __future__ import annotations

from datetime import datetime
import hashlib
import logging
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.event import Event
from app.db.models.source_url import SourceUrl
from app.services.extract.weekend_slicer import derive_weekend_events
from app.db.models.calendar_sync import CalendarSync

logger = logging.getLogger(__name__)

def store_extracted_events(
    session: Session,
    source_url: SourceUrl,
    extracted_events: list[dict[str, Any]],
    now: datetime,
    force_extract: bool = False,
) -> dict[str, int]:
    if (
        not force_extract
        and source_url.content_hash
        and source_url.last_extracted_hash == source_url.content_hash
    ):
        return {"created": 0, "updated": 0, "discarded_past": 0, "invalid": 0}

    created = 0
    updated = 0
    discarded_past = 0
    invalid = 0
    tz = ZoneInfo("Europe/Berlin")
    today = now.astimezone(tz).date()

    event_cache: dict[str, Event] = {}

    for item in extracted_events:
        if not isinstance(item, dict):
            continue

        title = _as_str(item.get("title"))
        start_time = _parse_datetime(item.get("start_time"), tz)
        end_time = _parse_datetime(item.get("end_time"), tz)
        location = _as_str(item.get("location")) or None

        if not title or not start_time:
            logger.info(
                "Skipping extracted item for url=%s reason=missing_title_or_start item=%s",
                source_url.url,
                _truncate_item(item),
            )
            invalid += 1
            continue

        if end_time is None:
            end_time = start_time

        derived_events = []
        if end_time.date() > start_time.date():
            derived_events = derive_weekend_events(
                title=title,
                start_time=start_time,
                end_time=end_time,
                location=location,
                description=_as_str(item.get("description")) or None,
                source_url=item.get("detail_url") or source_url.url,
            )
            if not derived_events:
                logger.info(
                    "Skipping multi-day event with no weekend days url=%s item=%s",
                    source_url.url,
                    _truncate_item(item),
                )
                invalid += 1
                continue
        else:
            derived_events = [
                {
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": location,
                    "description": _as_str(item.get("description")) or None,
                    "source_url": item.get("detail_url") or source_url.url,
                    "detail_url": item.get("detail_url"),
                }
            ]

        for derived in derived_events:
            if derived["end_time"].astimezone(tz).date() < today:
                discarded_past += 1
                continue

            external_key = _build_external_key(
                detail_url=derived.get("detail_url") or derived["source_url"],
                start_time=derived["start_time"],
            )
            existing = event_cache.get(external_key)
            if existing is None:
                stmt = select(Event).where(Event.external_key == external_key)
                existing = session.scalar(stmt)
            if existing:
                changed = _apply_updates(existing, derived)
                existing.external_key = external_key
                event_cache[external_key] = existing
                if changed:
                    _mark_for_resync(session, existing.id)
                    updated += 1
            elif external_key in event_cache:
                # already created in this batch, skip creating duplicate
                updated += 1
            else:
                event = Event(
                    title=derived["title"],
                    start_time=derived["start_time"],
                    end_time=derived["end_time"],
                    location=derived["location"],
                    description=derived["description"],
                    source_url=derived.get("detail_url") or derived["source_url"],
                    external_key=external_key,
                )
                session.add(event)
                event_cache[external_key] = event
                created += 1

    source_url.last_extracted_hash = source_url.content_hash
    source_url.last_extracted_at = now
    session.add(source_url)

    if discarded_past > 0:
        logger.info(
            "Discarded %s past events from url=%s",
            discarded_past,
            source_url.url,
        )

    return {
        "created": created,
        "updated": updated,
        "discarded_past": discarded_past,
        "invalid": invalid,
    }


def _as_str(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _parse_datetime(value: Any, tz: ZoneInfo) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)

    return parsed


def _build_external_key(detail_url: str, start_time: datetime) -> str:
    raw = f"{detail_url}|{start_time.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _truncate_item(item: Any, limit: int = 200) -> str:
    text = str(item)
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text


def _apply_updates(existing: Event, derived: dict[str, Any]) -> bool:
    changed = False
    for field in ["title", "start_time", "end_time", "location", "description", "source_url"]:
        new_val = derived.get(field) or (derived.get("detail_url") if field == "source_url" else getattr(existing, field))
        if getattr(existing, field) != new_val:
            setattr(existing, field, new_val)
            changed = True
    return changed


def _mark_for_resync(session: Session, event_id) -> None:
    session.query(CalendarSync).filter(CalendarSync.event_id == event_id).delete(synchronize_session=False)
    event = session.get(Event, event_id)
    if event:
        event.google_event_id = None
