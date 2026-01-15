from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy import select

from app.core.env import load_env
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.db.session import get_session
from app.logging import configure_logging
from app.services.extract.llm_event_extractor import extract_events_from_text
from app.services.extract.store_extracted_events import store_extracted_events

logger = logging.getLogger(__name__)


def run_extract_events() -> dict[str, int]:
    now = datetime.now(tz=timezone.utc)
    stats = {
        "sources_processed": 0,
        "events_created": 0,
        "sources_skipped_no_content": 0,
        "sources_skipped_unchanged_hash": 0,
        "sources_skipped_disabled_domain": 0,
    }

    session_gen = get_session()
    session = next(session_gen)
    try:
        sources = session.execute(
            select(SourceUrl, SourceDomain.is_allowed).join(
                SourceDomain, SourceDomain.id == SourceUrl.domain_id
            )
        ).all()

        for source_url, is_allowed in sources:
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

            stats["sources_processed"] += 1
            try:
                extracted = extract_events_from_text(
                    source_url.content_excerpt or "", source_url.url
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Extraction failed for url=%s: %s",
                    source_url.url,
                    exc,
                    exc_info=True,
                )
                continue

            created = store_extracted_events(session, source_url, extracted, now=now)
            stats["events_created"] += created

        session.commit()
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    return stats


def main() -> None:
    load_env()
    configure_logging()
    stats = run_extract_events()
    print(f"Sources processed: {stats['sources_processed']}")
    print(f"Events created: {stats['events_created']}")


if __name__ == "__main__":
    main()
