from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app.config import settings
from app.core.env import load_env
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine, get_session
from app.logging import configure_logging
from app.services.extract.llm_event_extractor import extract_events_from_text
from app.services.extract.series_cache import enrich_with_series_cache
from app.services.extract.store_extracted_events import store_extracted_events
from app.services.extract.muenchen_listing_parser import parse_listing
from app.services.fetch.http_fetcher import fetch_url_text
from app.services.fetch.listing_pagination import enumerate_listing_pages
from app.services.fetch.playwright_fetcher import fetch_url_playwright
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.sync_events import sync_unsynced_events
from sqlalchemy import select

from app.db.models.source_domain import get_or_create_domain
from app.db.models.source_url import SourceUrl
from app.db.models.source_url_discovery import SourceUrlDiscovery


def record_manual_discovery(session, source_url: SourceUrl) -> None:
    # Manual runs have no SearchResult provenance; skip discovery linking
    return None


def prepare_source_url(session, url: str, domain_row) -> SourceUrl:
    existing = session.scalar(select(SourceUrl).where(SourceUrl.url == url))
    if existing:
        return existing
    source_url = SourceUrl(
        url=url,
        domain_id=domain_row.id,
        fetch_status="ok",
        content_hash="manual",
    )
    session.add(source_url)
    session.flush()
    return source_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract all muenchen.de kinder listing pages.")
    parser.add_argument("--pages", type=int, default=None, help="Max pages to fetch")
    parser.add_argument("--persist", action="store_true", help="Persist events to DB")
    args = parser.parse_args()

    load_env()
    configure_logging()
    ensure_sqlite_schema(engine)

    start_url = "https://www.muenchen.de/veranstaltungen/event/kinder"
    now = datetime.now(tz=timezone.utc)

    session_gen = get_session()
    session = next(session_gen)
    created = 0
    try:
        domain_row = get_or_create_domain(session, "muenchen.de")
        source_url = prepare_source_url(session, start_url, domain_row)

        pages = list(
            enumerate_listing_pages(
                start_url=start_url,
                fetcher=fetch_url_text,
                max_pages=args.pages,
            )
        )
        if pages:
            logger.info("Listing pages to process: %s", ", ".join(pages))
        print(f"Found listing pages: {len(pages)}")

        all_events = []
        for page_url in pages:
            text, error, status = fetch_url_text(page_url)
            if error or text is None:
                continue
            listing_meta = parse_listing(text, page_url)
            events = extract_events_from_text(text, source_url=page_url)
            for idx, ev in enumerate(events):
                if idx < len(listing_meta):
                    detail_url = listing_meta[idx].get("detail_url")
                    address = listing_meta[idx].get("address")
                    if detail_url:
                        ev["detail_url"] = detail_url
                        ev["source_url"] = detail_url
                    if address:
                        ev["location"] = address
                ev.setdefault("source_url", page_url)
            all_events.extend(events)

        print(f"Extracted raw events: {len(all_events)}")
        if not args.persist:
            return

        def detail_fetcher(detail_url: str) -> str:
            text, error, status = fetch_url_text(detail_url)
            return text or ""

        enriched = enrich_with_series_cache(session, all_events, detail_fetcher, now=now)
        stats = store_extracted_events(
            session,
            source_url=source_url,
            extracted_events=enriched,
            now=now,
            force_extract=True,
        )
        created += stats["created"]
        session.commit()

        client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)
        sync_stats = sync_unsynced_events(session, client, now=now, limit=200, grace_hours=0)
        print(f"Persisted events: {created}, synced: {sync_stats['synced_count']}")
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
