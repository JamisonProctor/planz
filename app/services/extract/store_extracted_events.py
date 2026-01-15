from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models.event import Event
from app.db.models.source_url import SourceUrl

logger = logging.getLogger(__name__)

def store_extracted_events(
    session: Session,
    source_url: SourceUrl,
    extracted_events: list[dict[str, Any]],
    now: datetime,
) -> int:
    if source_url.content_hash and source_url.last_extracted_hash == source_url.content_hash:
        return 0

    created = 0
    tz = ZoneInfo("Europe/Berlin")

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
            continue

        if end_time is None:
            end_time = start_time

        event = Event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            location=location,
            description=None,
            source_url=source_url.url,
        )
        session.add(event)
        created += 1

    source_url.last_extracted_hash = source_url.content_hash
    source_url.last_extracted_at = now
    session.add(source_url)

    return created


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


def _truncate_item(item: Any, limit: int = 200) -> str:
    text = str(item)
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text
