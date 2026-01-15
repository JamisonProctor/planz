from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import get_session
from app.services.discovery.store_sources import store_discovered_sources
from app.services.llm.client import discover_munich_kids_event_sources


def main() -> None:
    sources = discover_munich_kids_event_sources()

    now = datetime.now(tz=timezone.utc)

    session_gen = get_session()
    session = next(session_gen)
    try:
        result = store_discovered_sources(session, sources, now)
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    print(f"Sources returned by LLM: {result['total_returned']}")
    print(f"New domains added: {result['new_domains']}")
    print(f"New URLs added: {result['new_urls']}")
    print(f"Existing URLs updated: {result['updated_urls']}")

    print("Top 10 active URLs:")
    for domain_str, url, name in result["active_urls"][:10]:
        label = name or "(no name)"
        print(f"- {domain_str} | {url} | {label}")


if __name__ == "__main__":
    main()
