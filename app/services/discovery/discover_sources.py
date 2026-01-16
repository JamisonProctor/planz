from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.core.urls import canonicalize_url, extract_domain
from app.services.discovery.source_policies import is_domain_allowed
from app.services.discovery.store_sources import store_discovered_sources
from app.services.fetch.http_fetcher import fetch_url_text

MIN_TEXT_LEN = 1500


def discover_and_store_sources(
    session,
    llm_client: Callable[[], list[dict[str, Any]]],
    http_fetcher: Callable[[str, float], tuple[str | None, str | None]] = fetch_url_text,
    now: datetime | None = None,
) -> dict[str, Any]:
    candidates = llm_client()
    accepted: list[dict[str, Any]] = []
    rejected = {
        "blocked_domain": 0,
        "fetch_failed": 0,
        "too_short": 0,
    }

    for item in candidates:
        if not isinstance(item, dict):
            continue

        raw_url = item.get("url", "")
        canonical = canonicalize_url(str(raw_url))
        if not canonical:
            continue

        domain = extract_domain(canonical)
        if not is_domain_allowed(domain):
            rejected["blocked_domain"] += 1
            continue

        text, error = http_fetcher(canonical, 5.0)
        if error or text is None:
            rejected["fetch_failed"] += 1
            continue

        if len(text) < MIN_TEXT_LEN:
            rejected["too_short"] += 1
            continue

        accepted.append(
            {
                "url": canonical,
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "reason": item.get("reason", ""),
            }
        )

    if now is None:
        now = datetime.utcnow()

    store_discovered_sources(session, accepted, now)

    return {
        "total_candidates": len(candidates),
        "accepted": len(accepted),
        "rejected": rejected,
        "accepted_urls": [item["url"] for item in accepted],
    }
