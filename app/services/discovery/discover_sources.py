from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Callable

from app.core.urls import canonicalize_url, extract_domain
from app.services.discovery.source_policies import is_domain_allowed
from app.services.discovery.store_sources import store_discovered_sources
from app.services.fetch.http_fetcher import fetch_url_text

MIN_TEXT_LEN = 1500
PREFERRED_URL_KEYWORDS = ["termine", "kalender", "veranstaltungen", "programm"]
ARCHIVE_SIGNALS = ["rückblick", "archiv"]

logger = logging.getLogger(__name__)


def _is_preferred_url(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in PREFERRED_URL_KEYWORDS)


def _has_archive_or_past_signals(text: str, current_year: int) -> bool:
    lower = text.lower()
    if any(signal in lower for signal in ARCHIVE_SIGNALS):
        return True

    for token in lower.split():
        if token.isdigit() and len(token) == 4:
            try:
                year = int(token)
            except ValueError:
                continue
            if year < current_year:
                return True

    return False


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
        "archive_or_past": 0,
    }

    current_year = (now or datetime.utcnow()).year

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

        if _has_archive_or_past_signals(text, current_year):
            rejected["archive_or_past"] += 1
            logger.info("Rejected archive/past url=%s", canonical)
            continue

        preferred = _is_preferred_url(canonical)
        if preferred:
            logger.info("Accepted preferred url=%s", canonical)
        else:
            logger.info("Accepted non-preferred url=%s", canonical)

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
