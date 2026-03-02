from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import logging

from app.config import settings
from app.core.env import load_env
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine, get_session
from app.logging import configure_logging
from app.services.extract.store_extracted_events import store_extracted_events
from app.services.extract.muenchen_listing_parser import parse_listing
from app.services.fetch.http_fetcher import fetch_url_text
from app.services.fetch.listing_pagination import enumerate_listing_pages
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.sync_events import sync_unsynced_events
from app.utils.heartbeat import start_heartbeat
from app.utils.timing import RunStats, Timer, format_duration
from sqlalchemy import select

from app.db.models.source_domain import get_or_create_domain
from app.db.models.source_url import SourceUrl
from app.services.extract.weekend_slicer import _is_recommendation_day

logger = logging.getLogger(__name__)
TICKET_PREFIX = "🎟 "
_MONTHS = {
    "JAN": 1,
    "JANUAR": 1,
    "FEB": 2,
    "FEBRUAR": 2,
    "MAERZ": 3,
    "MÄRZ": 3,
    "APR": 4,
    "APRIL": 4,
    "MAI": 5,
    "JUN": 6,
    "JUNI": 6,
    "JUL": 7,
    "JULI": 7,
    "AUG": 8,
    "AUGUST": 8,
    "SEP": 9,
    "SEPT": 9,
    "SEPTEMBER": 9,
    "OKT": 10,
    "OKTOBER": 10,
    "NOV": 11,
    "NOVEMBER": 11,
    "DEZ": 12,
    "DEZEMBER": 12,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract all muenchen.de kinder listing pages.")
    parser.add_argument("--pages", type=int, default=None, help="Max pages to fetch")
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Only process the first N unique listing items (each may expand to multiple date rows)",
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
    max_items: int | None = None,
) -> list[dict]:
    events: list[dict] = []
    listing_meta = parse_listing(listing_html, listing_url)
    items_processed = 0
    for item in listing_meta:
        if max_items is not None and items_processed >= max_items:
            break
        detail_url = item.get("detail_url")
        address = item.get("address")
        ticket_url = item.get("ticket_url")
        extracted = _structured_events_from_listing_item(item)
        if not extracted:
            continue
        items_processed += 1
        for ev in extracted:
            if detail_url:
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


def _structured_events_from_listing_item(item: dict) -> list[dict]:
    title = item.get("title")
    start_time = item.get("start_time")
    if not isinstance(title, str) or not title.strip() or not isinstance(start_time, str):
        return []
    detail_url = item.get("detail_url")
    ticket_url = item.get("ticket_url")
    source_url = ticket_url or detail_url
    if not isinstance(source_url, str) or not source_url:
        return []

    events: list[dict] = []
    for slot_start, slot_end, is_candidate in _expand_visible_date_range(
        item=item,
        start_time=start_time,
        end_time=item.get("end_time"),
    ):
        event = {
            "title": title.strip(),
            "start_time": slot_start,
            "location": item.get("location") or item.get("address"),
            "source_url": source_url,
            "is_calendar_candidate": is_candidate,
        }
        if detail_url:
            event["detail_url"] = detail_url
        if isinstance(item.get("raw_schedule"), str):
            event["raw_schedule"] = item["raw_schedule"]
        if slot_end:
            event["end_time"] = slot_end
        events.append(event)
    return events


def _expand_visible_date_range(
    *,
    item: dict,
    start_time: str,
    end_time: str | None,
) -> list[tuple[str, str | None, bool]]:
    start_dt = datetime.fromisoformat(start_time)
    range_bounds = _extract_date_range_bounds(item, reference_year=start_dt.year)
    if range_bounds is None:
        return [(start_time, end_time if isinstance(end_time, str) else None, True)]

    range_start, range_end = range_bounds
    end_dt = datetime.fromisoformat(end_time) if isinstance(end_time, str) else None
    slots: list[tuple[str, str | None, bool]] = []
    current = range_start
    while current <= range_end:
        slot_start = _copy_time_to_date(start_dt, current)
        slot_end = _copy_time_to_date(end_dt, current) if end_dt else None
        if slot_end and slot_end <= slot_start:
            slot_end = slot_start.replace(hour=23, minute=59, second=0, microsecond=0)
        slots.append(
            (
                slot_start.isoformat(),
                slot_end.isoformat() if slot_end else None,
                _is_recommendation_day(current),
            )
        )
        current = current.fromordinal(current.toordinal() + 1)
    return slots


def _extract_date_range_bounds(item: dict, reference_year: int) -> tuple[date, date] | None:
    range_start = _parse_iso_date(item.get("range_start_date"))
    range_end = _parse_iso_date(item.get("range_end_date"))
    if range_start and range_end and range_end > range_start:
        return range_start, range_end

    listing_text = item.get("listing_text") or ""
    import re

    match = re.search(
        r"(\d{2})\s+([A-Za-zÄÖÜäöüß\.]+)\s+bis\s+(\d{2})\s+([A-Za-zÄÖÜäöüß\.]+)",
        listing_text,
    )
    if not match:
        return None
    start_day, start_month_name, end_day, end_month_name = match.groups()
    start_month = _parse_german_month(start_month_name)
    end_month = _parse_german_month(end_month_name)
    if start_month is None or end_month is None:
        return None

    start_date = date(reference_year, start_month, int(start_day))
    end_year = reference_year + 1 if end_month < start_month else reference_year
    end_date = date(end_year, end_month, int(end_day))
    return start_date, end_date


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_german_month(value: str) -> int | None:
    normalized = value.strip().rstrip(".").upper()
    normalized = (
        normalized.replace("Ä", "AE")
        .replace("Ö", "OE")
        .replace("Ü", "UE")
    )
    return _MONTHS.get(normalized)


def _copy_time_to_date(source: datetime, target_date: date) -> datetime:
    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        source.hour,
        source.minute,
        source.second,
        source.microsecond,
        tzinfo=source.tzinfo,
    )


def _resolve_sync_limit(max_events: int | None) -> int:
    if max_events is not None:
        return max_events * 20  # each listing item may expand to many date rows
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
                    max_items=remaining_events,
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

        with Timer("persist") as t_persist:
            results = store_extracted_events(
                session,
                source_url=source_url,
                extracted_events=all_events,
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
