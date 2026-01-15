from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy import select

from app.core.env import load_env
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.db.session import get_session
from app.logging import configure_logging
from app.services.fetch.http_fetcher import fetch_url_text
from app.services.fetch.store_fetch_result import store_fetch_result

logger = logging.getLogger(__name__)


def run_fetch_sources() -> dict[str, int]:
    ok_count = 0
    error_count = 0
    now = datetime.now(tz=timezone.utc)

    session_gen = get_session()
    session = next(session_gen)
    try:
        urls = session.scalars(
            select(SourceUrl)
            .join(SourceDomain, SourceDomain.id == SourceUrl.domain_id)
            .where(SourceDomain.is_allowed.is_(True))
        ).all()

        for source_url in urls:
            text, error = fetch_url_text(source_url.url)
            store_fetch_result(session, source_url, text=text, error=error, now=now)
            if text is not None:
                ok_count += 1
            else:
                logger.error(
                    "Fetch failed for url=%s error=%s",
                    source_url.url,
                    error,
                )
                error_count += 1

        session.commit()
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    return {"fetched_ok": ok_count, "fetched_error": error_count}


def main() -> None:
    load_env()
    configure_logging()
    stats = run_fetch_sources()
    print(f"Fetched OK: {stats['fetched_ok']}")
    print(f"Fetched errors: {stats['fetched_error']}")


if __name__ == "__main__":
    main()
