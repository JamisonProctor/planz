from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Callable

from app.config import settings
from app.core.env import load_env
from app.core.urls import extract_domain
from app.db.models.source_domain import get_or_create_domain
from app.db.models.source_url import SourceUrl
from app.db.session import get_session
from app.logging import configure_logging
from app.services.extract.llm_event_extractor import extract_events_from_text
from app.services.extract.store_extracted_events import store_extracted_events
from app.services.fetch.http_fetcher import fetch_url_text


def extract_single(
    url: str,
    fetcher: Callable[..., tuple[str | None, str | None] | tuple[str | None, str | None, int | None]],
    extractor: Callable[[str, str], list[dict[str, Any]]],
    persist: bool = False,
) -> dict[str, Any]:
    result = fetcher(url, 10.0)
    if len(result) == 3:
        text, error, status = result  # type: ignore[misc]
    else:
        text, error = result  # type: ignore[misc]
        status = None

    content_length = len(text) if text else 0
    events: list[dict[str, Any]] = []
    if text and not error:
        try:
            events = extractor(text, source_url=url)
        except Exception:
            events = []

    summary = {
        "url_final": url,
        "http_status": status,
        "content_length": content_length,
        "extracted_events_count": len(events),
        "events": events,
    }

    print(
        f"url_final={summary['url_final']} http_status={summary['http_status']} "
        f"content_length={summary['content_length']} extracted_events_count: {summary['extracted_events_count']}"
    )
    for event in events[:5]:
        title = event.get("title")
        start = event.get("start_time")
        print(f"- {start} {title}")

    if persist and events:
        session_gen = get_session()
        session = next(session_gen)
        try:
            domain_row = get_or_create_domain(session, extract_domain(url))
            source_url = SourceUrl(
                url=url,
                domain_id=domain_row.id,
                fetch_status="ok",
                content_hash="manual",
            )
            session.add(source_url)
            session.flush()
            store_extracted_events(
                session,
                source_url=source_url,
                extracted_events=events,
                now=datetime.now(tz=timezone.utc),
                force_extract=True,
            )
            session.commit()
        finally:
            try:
                next(session_gen)
            except StopIteration:
                pass

    return summary


def main() -> None:
    load_env()
    configure_logging()

    parser = argparse.ArgumentParser(description="Extract events from a single URL without DB persistence.")
    parser.add_argument("url", help="URL to fetch and extract")
    parser.add_argument("--persist", action="store_true", help="Persist extracted events to DB")
    args = parser.parse_args()

    extract_single(
        url=args.url,
        fetcher=fetch_url_text,
        extractor=extract_events_from_text,
        persist=args.persist,
    )


if __name__ == "__main__":
    main()
