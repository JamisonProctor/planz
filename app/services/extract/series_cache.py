from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.urls import extract_domain
from app.db.models.event_series import EventSeries


def _series_key(item: dict[str, Any]) -> str:
    detail_url = item.get("detail_url")
    if detail_url:
        return detail_url
    title = (item.get("title") or "").strip().lower()
    location = (item.get("location") or "").strip().lower()
    domain = extract_domain(item.get("source_url") or "") if item.get("source_url") else ""
    return f"{domain}:{title}:{location}"


def enrich_with_series_cache(
    session: Session,
    events: list[dict[str, Any]],
    detail_fetcher: Callable[[str], str],
    now: datetime,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    cache: dict[str, EventSeries] = {}

    for item in events:
        key = _series_key(item)
        if key in cache:
            series = cache[key]
        else:
            series = session.scalar(select(EventSeries).where(EventSeries.series_key == key))
            if series is None:
                description = None
                detail_url = item.get("detail_url")
                if detail_url:
                    description = detail_fetcher(detail_url)
                series = EventSeries(
                    series_key=key,
                    detail_url=item.get("detail_url"),
                    title=item.get("title"),
                    venue=item.get("location"),
                    description=description,
                    updated_at=now,
                )
                session.add(series)
                session.flush()
            cache[key] = series

        new_item = dict(item)
        if series.description:
            new_item["description"] = series.description
        enriched.append(new_item)

    session.commit()
    return enriched
