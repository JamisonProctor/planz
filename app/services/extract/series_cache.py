from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.urls import extract_domain
from app.db.models.event_series import EventSeries
from app.services.extract.html_to_text import HtmlToText
from app.services.llm.summarizer import EventPageSummary, summarize_event_page


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
    summarizer: Callable[[str], EventPageSummary | None] = summarize_event_page,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    cache: dict[str, EventSeries] = {}
    html_to_text = HtmlToText()

    for item in events:
        key = _series_key(item)
        if key in cache:
            series = cache[key]
        else:
            series = session.scalar(select(EventSeries).where(EventSeries.series_key == key))
            if series is None:
                result: EventPageSummary | None = None
                fetch_url = item.get("detail_url") or item.get("source_url")
                if fetch_url:
                    page_text = html_to_text.extract(detail_fetcher(fetch_url))
                    result = summarizer(page_text) if page_text else None
                series = EventSeries(
                    series_key=key,
                    detail_url=item.get("detail_url"),
                    title=item.get("title"),
                    venue=item.get("location"),
                    description=result.summary if result else None,
                    venue_address=result.address if result else None,
                    is_paid=result.is_paid if result else False,
                    category=result.category if result else None,
                    updated_at=now,
                )
                session.add(series)
                session.flush()
            elif series.description is None or series.venue_address is None or series.category is None:
                # Existing series missing summary, address, or category — fill in now
                fetch_url = series.detail_url or item.get("source_url")
                if fetch_url:
                    page_text = html_to_text.extract(detail_fetcher(fetch_url))
                    if page_text:
                        result = summarizer(page_text)
                        if result:
                            if result.summary:
                                series.description = result.summary
                            series.venue_address = result.address
                            series.is_paid = result.is_paid
                            series.category = result.category
                            session.flush()
            cache[key] = series

        new_item = dict(item)
        if series.description:
            new_item["description"] = series.description
        if series.venue_address:
            new_item["venue_address"] = series.venue_address
        new_item["is_paid"] = series.is_paid
        new_item["category"] = series.category
        enriched.append(new_item)

    session.commit()
    return enriched
