from __future__ import annotations

from datetime import datetime, timezone

from app.core.env import load_env
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine, get_session
from app.logging import configure_logging
from app.services.discovery.discover_sources import discover_and_store_sources
from app.services.llm.client import discover_munich_kids_event_sources


def main() -> None:
    load_env()
    configure_logging()
    ensure_sqlite_schema(engine)
    now = datetime.now(tz=timezone.utc)

    session_gen = get_session()
    session = next(session_gen)
    try:
        result = discover_and_store_sources(
            session,
            llm_client=discover_munich_kids_event_sources,
            now=now,
        )
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    rejected = result["rejected"]
    print(f"Candidates returned: {result['total_candidates']}")
    print(f"Accepted: {result['accepted']}")
    print(
        "Rejected: blocked_domain={blocked_domain}, fetch_failed={fetch_failed}, "
        "too_short={too_short}".format(**rejected)
    )
    print("Top accepted URLs:")
    for url in result["accepted_urls"][:10]:
        print(f"- {url}")


if __name__ == "__main__":
    main()
