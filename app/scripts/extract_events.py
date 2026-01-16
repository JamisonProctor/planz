from __future__ import annotations

from datetime import datetime, timezone

from app.core.env import load_env
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine, get_session
from app.logging import configure_logging
from app.services.extract.llm_event_extractor import extract_events_from_text
from app.services.extract.extract_and_store import extract_and_store_for_sources


def run_extract_events() -> dict[str, int]:
    now = datetime.now(tz=timezone.utc)
    stats: dict[str, int] = {}

    session_gen = get_session()
    session = next(session_gen)
    try:
        stats = extract_and_store_for_sources(
            session, extractor=extract_events_from_text, now=now
        )
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    return stats


def main() -> None:
    load_env()
    configure_logging()
    ensure_sqlite_schema(engine)
    stats = run_extract_events()
    print(f"Sources processed: {stats['sources_processed']}")
    print(f"Sources skipped (no content): {stats['sources_skipped_no_content']}")
    print(f"Sources skipped (unchanged hash): {stats['sources_skipped_unchanged_hash']}")
    print(f"Sources skipped (disabled domain): {stats['sources_skipped_disabled_domain']}")
    print(f"Sources empty extraction: {stats['sources_empty_extraction']}")
    print(f"Sources error extraction: {stats['sources_error_extraction']}")
    print(f"Events created: {stats['events_created_total']}")


if __name__ == "__main__":
    main()
