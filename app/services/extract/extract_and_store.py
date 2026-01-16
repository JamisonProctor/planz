from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy import select

from app.core.env import is_force_extract_enabled
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.services.extract.store_extracted_events import store_extracted_events

logger = logging.getLogger(__name__)


def extract_and_store_for_sources(
    session,
    extractor: Callable[[str, str], list[dict]],
    now: datetime,
) -> dict[str, int]:
    stats = {
        "sources_processed": 0,
        "events_created_total": 0,
        "sources_skipped_no_content": 0,
        "sources_skipped_unchanged_hash": 0,
        "sources_skipped_disabled_domain": 0,
        "sources_empty_extraction": 0,
        "sources_error_extraction": 0,
        "sources_past_only": 0,
    }

    force_extract = is_force_extract_enabled()
    if force_extract:
        logger.info("Force extraction enabled: ignoring content hash")

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

        if not force_extract:
            if (
                source_url.content_hash
                and source_url.last_extracted_hash == source_url.content_hash
            ):
                stats["sources_skipped_unchanged_hash"] += 1
                continue

        stats["sources_processed"] += 1
        try:
            extracted = extractor(source_url.content_excerpt or "", source_url.url)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Extraction failed for url=%s: %s",
                source_url.url,
                exc,
                exc_info=True,
            )
            source_url.last_extraction_status = "error"
            source_url.last_extraction_error = str(exc)
            source_url.last_extraction_count = None
            stats["sources_error_extraction"] += 1
            continue

        result = store_extracted_events(
            session,
            source_url,
            extracted,
            now=now,
            force_extract=force_extract,
        )
        created = result["created"]
        stats["events_created_total"] += created

        if created == 0 and result["discarded_past"] > 0 and result["invalid"] == 0:
            source_url.last_extraction_status = "past_only"
            source_url.last_extraction_count = 0
            stats["sources_past_only"] += 1
        elif created == 0:
            source_url.last_extraction_status = "empty"
            source_url.last_extraction_count = 0
            stats["sources_empty_extraction"] += 1
        else:
            source_url.last_extraction_status = "ok"
            source_url.last_extraction_count = created

        source_url.last_extraction_error = None

    session.commit()
    return stats
