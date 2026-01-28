from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from time import monotonic

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
from app.utils.heartbeat import start_heartbeat
from app.utils.timing import RunStats, Timer, format_duration
from sqlalchemy import select

from app.db.models.source_domain import get_or_create_domain
from app.db.models.source_url import SourceUrl
from app.db.models.source_url_discovery import SourceUrlDiscovery

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract all muenchen.de kinder listing pages.")
    parser.add_argument("--pages", type=int, default=None, help="Max pages to fetch")
    parser.add_argument("--persist", action="store_true", help="Persist events to DB")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip calendar sync (for dry runs or data-only refresh)",
    )
    return parser


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
    parser = build_parser()
    args = parser.parse_args()

    load_env()
    configure_logging("DEBUG" if args.verbose else None)
    ensure_sqlite_schema(engine)

    start_url = "https://www.muenchen.de/veranstaltungen/event/kinder"
    now = datetime.now(tz=timezone.utc)

    session_gen = get_session()
    session = next(session_gen)
    created = 0
    updated = 0
    try:
        domain_row = get_or_create_domain(session, "muenchen.de")
        source_url = prepare_source_url(session, start_url, domain_row)

        overall_timer = Timer("overall")
        overall_timer.__enter__()
        pages = list(
            enumerate_listing_pages(
                start_url=start_url,
                fetcher=fetch_url_text,
                max_pages=args.pages,
            )
        )
        if pages:
            logger.info("Listing pages to process: %s", ", ".join(pages))
        logger.info("Found listing pages: %s", len(pages))

        all_events = []
        run_stats: list[RunStats] = []
        for idx, page_url in enumerate(pages, 1):
            stats = RunStats(page_index=idx, page_total=len(pages))
            with Timer("fetch") as t_fetch:
                text, error, status = fetch_url_text(page_url)
            stats.fetch_s = t_fetch.elapsed
            if error or text is None:
                stats.errors_count += 1
                stats.total_elapsed_s = t_fetch.elapsed
                stats.log_status(logger)
                run_stats.append(stats)
                continue
            listing_meta = parse_listing(text, page_url)
            stop_hb = start_heartbeat("extract_page", interval_s=30, logger=logger)
            with Timer("extract") as t_extract:
                events = extract_events_from_text(text, source_url=page_url)
            stop_hb()
            stats.extract_s = t_extract.elapsed
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
            stats.events_extracted = len(events)
            stats.total_elapsed_s = stats.fetch_s + stats.extract_s
            stats.log_status(logger)
            run_stats.append(stats)

        logger.info("Extracted raw events: %s", len(all_events))
        if not args.persist:
            overall_timer.__exit__(None, None, None)
            totals = RunStats.combine(run_stats)
            totals.total_elapsed_s = overall_timer.elapsed
            logger.info(
                "DONE pages=%s fetch=%s extract=%s persist=%s sync=%s events=%s errors=%s total=%s",
                totals.page_total,
                format_duration(totals.fetch_s),
                format_duration(totals.extract_s),
                format_duration(totals.persist_s),
                format_duration(totals.sync_s),
                totals.events_extracted,
                totals.errors_count,
                format_duration(totals.total_elapsed_s),
            )
            return

        def detail_fetcher(detail_url: str) -> str:
            text, error, status = fetch_url_text(detail_url)
            return text or ""

        with Timer("persist") as t_persist:
            enriched = enrich_with_series_cache(session, all_events, detail_fetcher, now=now)
            results = store_extracted_events(
                session,
                source_url=source_url,
                extracted_events=enriched,
                now=now,
                force_extract=True,
            )
            created += results["created"]
            updated += results["updated"]
            session.commit()

        sync_stats = {"synced_count": 0}
        t_sync = Timer("sync")
        if not args.no_sync:
            client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)
            with t_sync:
                sync_stats = sync_unsynced_events(session, client, now=now, limit=200, grace_hours=0)

        overall_timer.__exit__(None, None, None)
        totals = RunStats.combine(run_stats)
        totals.persist_s = t_persist.elapsed
        totals.sync_s = t_sync.elapsed
        totals.events_new = created
        totals.events_updated = updated
        totals.events_extracted = len(all_events)
        totals.total_elapsed_s = overall_timer.elapsed

        logger.info(
            "DONE pages=%s fetch=%s extract=%s persist=%s sync=%s events=%s new=%s updated=%s errors=%s total=%s",
            totals.page_total,
            format_duration(totals.fetch_s),
            format_duration(totals.extract_s),
            format_duration(totals.persist_s),
            format_duration(totals.sync_s),
            totals.events_extracted,
            totals.events_new,
            totals.events_updated,
            totals.errors_count,
            format_duration(totals.total_elapsed_s),
        )
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
