from __future__ import annotations

from datetime import datetime, timezone

from app.core.env import load_env
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine, get_session
from app.logging import configure_logging
from app.services.fetch.http_fetcher import fetch_url_text
from app.services.search.openai_web_search import OpenAIWebSearchProvider
from app.services.search.seed_sources import search_and_seed_sources


def main() -> None:
    load_env()
    configure_logging()
    ensure_sqlite_schema(engine)

    now = datetime.now(tz=timezone.utc)
    session_gen = get_session()
    session = next(session_gen)
    try:
        provider = OpenAIWebSearchProvider()
        stats = search_and_seed_sources(
            session=session,
            provider_search=provider.search,
            fetcher=fetch_url_text,
            now=now,
            location="Munich, Germany",
            window_days=30,
        )
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    rejected = stats["rejected"]
    soft = stats["accepted_soft_signals"]
    caps = stats["caps_hit"]
    print(f"Queries executed: {stats['queries_executed']}")
    print(f"Total results: {stats['total_results']}")
    print(f"Unique candidate urls: {stats['unique_candidates']}")
    print(f"Accepted urls: {stats['accepted']}")
    print(
        "Rejected: blocked_domain={blocked_domain}, http_blocked={http_blocked}, "
        "fetch_failed={fetch_failed}, too_short={too_short}".format(**rejected)
    )
    print(
        "Accepted soft signals: archive_signals={archive_signals}, "
        "no_date_tokens={no_date_tokens}, js_suspected={js_suspected}".format(
            **soft
        )
    )
    if caps["accepted"] or caps["fetched"]:
        print(
            "Caps hit: accepted={accepted}, fetched={fetched}".format(**caps)
        )
    print("Accepted URLs:")
    for url in stats["accepted_urls"]:
        print(f"- {url}")


if __name__ == "__main__":
    main()
