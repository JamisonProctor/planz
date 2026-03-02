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
TICKET_PREFIX = "🎟 "


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract all muenchen.de kinder listing pages.")
    parser.add_argument("--pages", type=int, default=None, help="Max pages to fetch")
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Only process the first N listing entries across the run",
    )
    parser.add_argument("--persist", action="store_true", help="Persist events to DB")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--sync-days",
        type=int,
        default=None,
        help="Only sync events starting within this many days from now",
    )
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


def extract_detail_events_from_listing(
    *,
    listing_html: str,
    listing_url: str,
    fetcher,
    extractor,
    max_items: int | None = None,
    allow_llm_fallback: bool = True,
) -> list[dict]:
    events: list[dict] = []
    listing_meta = parse_listing(listing_html, listing_url)
    for item in listing_meta:
        if max_items is not None and len(events) >= max_items:
            break
        detail_url = item["detail_url"]
        address = item.get("address")
        ticket_url = item.get("ticket_url")
        listing_text = item.get("listing_text") or ""
        extracted = _structured_events_from_listing_item(item)
        if not extracted and allow_llm_fallback:
            text, error, status = fetcher(detail_url)
            if error or text is None:
                logger.info(
                    "Skipping detail page fetch url=%s status=%s error=%s",
                    detail_url,
                    status,
                    error,
                )
                continue

            combined_text = _combine_listing_and_detail_text(listing_text, text)
            extracted = extractor(combined_text, source_url=detail_url)
        if max_items is not None:
            remaining_slots = max_items - len(events)
            if remaining_slots <= 0:
                break
            extracted = extracted[:remaining_slots]
        for ev in extracted:
            ev["detail_url"] = detail_url
            if ticket_url:
                ev["ticket_url"] = ticket_url
                ev["source_url"] = ticket_url
                title = ev.get("title")
                if isinstance(title, str) and title and not title.startswith(TICKET_PREFIX):
                    ev["title"] = f"{TICKET_PREFIX}{title}"
            else:
                ev["source_url"] = detail_url
            if address and not ev.get("location"):
                ev["location"] = address
        events.extend(extracted)
    return events


def _combine_listing_and_detail_text(listing_text: str, detail_text: str) -> str:
    if listing_text:
        return f"Listing context:\n{listing_text}\n\nDetail page:\n{detail_text}"
    return f"Detail page:\n{detail_text}"


def _structured_events_from_listing_item(item: dict) -> list[dict]:
    title = item.get("title")
    start_time = item.get("start_time")
    if not isinstance(title, str) or not title.strip() or not isinstance(start_time, str):
        return []

    event = {
        "title": title.strip(),
        "start_time": start_time,
        "location": item.get("location") or item.get("address"),
        "detail_url": item["detail_url"],
        "source_url": item["detail_url"],
    }
    if isinstance(item.get("raw_schedule"), str):
        event["raw_schedule"] = item["raw_schedule"]
    if isinstance(item.get("end_time"), str):
        event["end_time"] = item["end_time"]
    return [event]


def _resolve_sync_limit(max_events: int | None) -> int:
    if max_events is not None:
        return max_events
    return 200


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
        remaining_events = args.max_events
        for idx, page_url in enumerate(pages, 1):
            if remaining_events is not None and remaining_events <= 0:
                break
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
            stop_hb = start_heartbeat("extract_page", interval_s=30, logger=logger)
            with Timer("extract") as t_extract:
                events = extract_detail_events_from_listing(
                    listing_html=text,
                    listing_url=page_url,
                    fetcher=fetch_url_text,
                    extractor=extract_events_from_text,
                    max_items=remaining_events,
                    allow_llm_fallback=args.max_events is None,
                )
            stop_hb()
            stats.extract_s = t_extract.elapsed
            all_events.extend(events)
            if remaining_events is not None:
                remaining_events = max(remaining_events - len(events), 0)
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
                sync_stats = sync_unsynced_events(
                    session,
                    client,
                    now=now,
                    limit=_resolve_sync_limit(args.max_events),
                    grace_hours=0,
                    max_days=args.sync_days,
                )

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
