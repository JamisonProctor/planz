from __future__ import annotations

from datetime import datetime, timezone
import os

from sqlalchemy import func, select

from app.core.env import load_env
from app.config import settings
from app.db.models.calendar_sync import CalendarSync
from app.db.models.event import Event
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine, get_session
from app.logging import configure_logging
from app.scripts.extract_events import run_extract_events
from app.scripts.fetch_sources import run_fetch_sources
from app.services.calendar.google_calendar_service import GoogleCalendarClient
from app.services.calendar.sync_events import sync_unsynced_events


def _source_inventory(session) -> dict[str, int]:
    total = session.scalar(select(func.count(SourceUrl.id))) or 0
    allowed = session.scalar(
        select(func.count(SourceUrl.id))
        .join(SourceDomain, SourceDomain.id == SourceUrl.domain_id)
        .where(SourceDomain.is_allowed.is_(True))
    ) or 0
    disabled = total - allowed
    return {"total": total, "allowed": allowed, "disabled": disabled}


def _extraction_inventory(session) -> dict[str, int]:
    stats = {
        "eligible": 0,
        "sources_skipped_no_content": 0,
        "sources_skipped_unchanged_hash": 0,
        "sources_skipped_disabled_domain": 0,
    }
    rows = session.execute(
        select(SourceUrl, SourceDomain.is_allowed).join(
            SourceDomain, SourceDomain.id == SourceUrl.domain_id
        )
    ).all()

    for source_url, is_allowed in rows:
        if not is_allowed:
            stats["sources_skipped_disabled_domain"] += 1
            continue
        if source_url.fetch_status != "ok" or source_url.content_excerpt is None:
            stats["sources_skipped_no_content"] += 1
            continue
        if (
            source_url.content_hash
            and source_url.last_extracted_hash == source_url.content_hash
        ):
            stats["sources_skipped_unchanged_hash"] += 1
            continue
        stats["eligible"] += 1

    return stats


def _sync_inventory(session, now: datetime) -> dict[str, int]:
    future_synced = session.scalar(
        select(func.count(Event.id))
        .join(CalendarSync, CalendarSync.event_id == Event.id)
        .where(Event.start_time >= now)
    ) or 0
    future_unsynced = session.scalar(
        select(func.count(Event.id))
        .outerjoin(CalendarSync, CalendarSync.event_id == Event.id)
        .where(CalendarSync.id.is_(None))
        .where(Event.start_time >= now)
    ) or 0
    past_unsynced = session.scalar(
        select(func.count(Event.id))
        .outerjoin(CalendarSync, CalendarSync.event_id == Event.id)
        .where(CalendarSync.id.is_(None))
        .where(Event.start_time < now)
    ) or 0

    return {
        "events_skipped_already_synced": future_synced,
        "events_skipped_past": past_unsynced,
        "events_eligible": future_unsynced,
    }


def run_weekly_pipeline(
    session,
    now: datetime,
    fetch_runner=run_fetch_sources,
    extract_runner=run_extract_events,
    sync_runner=sync_unsynced_events,
    calendar_client_factory=GoogleCalendarClient,
) -> dict[str, int]:
    inventory = _source_inventory(session)
    print(
        "Source URLs total: {total}, allowed: {allowed}, disabled: {disabled}".format(
            **inventory
        )
    )
    if inventory["allowed"] == 0:
        print("No allowed sources to fetch. Run discovery or add sources.")

    fetch_stats = fetch_runner()
    if fetch_stats["fetched_error"] > 0:
        print("See logs for details.")

    extraction_inventory = _extraction_inventory(session)
    openai_available = bool(os.getenv("OPENAI_API_KEY"))
    if extraction_inventory["eligible"] > 0 and not openai_available:
        print("OPENAI_API_KEY missing: extraction skipped.")
        extract_stats = {
            "sources_processed": 0,
            "events_created_total": 0,
            "sources_skipped_no_content": extraction_inventory[
                "sources_skipped_no_content"
            ],
            "sources_skipped_unchanged_hash": extraction_inventory[
                "sources_skipped_unchanged_hash"
            ],
            "sources_skipped_disabled_domain": extraction_inventory[
                "sources_skipped_disabled_domain"
            ],
            "sources_empty_extraction": 0,
            "sources_error_extraction": 0,
            "sources_past_only": 0,
        }
    else:
        extract_stats = extract_runner()

    if (
        extract_stats["sources_processed"] == 0
        and extract_stats["sources_skipped_unchanged_hash"] > 0
        and extraction_inventory["eligible"] == 0
    ):
        print("Extraction skipped: all content hashes unchanged.")

    client = None
    if calendar_client_factory is not None:
        client = calendar_client_factory(calendar_id=settings.GOOGLE_CALENDAR_ID)
    sync_result = sync_runner(session, client, now=now, limit=50, grace_hours=0)
    if isinstance(sync_result, int):
        sync_stats = {
            "synced_count": sync_result,
            "skipped_already_synced": 0,
            "skipped_too_old": 0,
        }
    else:
        sync_stats = sync_result

    print(f"Fetched OK: {fetch_stats['fetched_ok']}")
    print(f"Fetched errors: {fetch_stats['fetched_error']}")
    print(f"Sources processed: {extract_stats['sources_processed']}")
    print(f"Events created: {extract_stats['events_created_total']}")
    print(
        f"Sources skipped (no content): {extract_stats['sources_skipped_no_content']}"
    )
    print(
        f"Sources skipped (unchanged hash): {extract_stats['sources_skipped_unchanged_hash']}"
    )
    print(
        f"Sources skipped (disabled domain): {extract_stats['sources_skipped_disabled_domain']}"
    )
    print(
        f"Sources empty extraction: {extract_stats['sources_empty_extraction']}"
    )
    print(
        f"Sources error extraction: {extract_stats['sources_error_extraction']}"
    )
    print(f"Sources past-only: {extract_stats['sources_past_only']}")
    print(f"Events synced: {sync_stats['synced_count']}")
    print(
        f"Events skipped (already synced): {sync_stats['skipped_already_synced']}"
    )
    print(f"Events skipped (too old): {sync_stats['skipped_too_old']}")

    return {
        **inventory,
        **fetch_stats,
        **extract_stats,
        **sync_stats,
        "events_synced": sync_stats["synced_count"],
    }


def main() -> None:
    load_env()
    configure_logging()
    ensure_sqlite_schema(engine)

    now = datetime.now(tz=timezone.utc)
    session_gen = get_session()
    session = next(session_gen)
    try:
        run_weekly_pipeline(session=session, now=now)
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
