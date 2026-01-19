from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Callable

from sqlalchemy import select

from app.db.models.search_query import SearchQuery
from app.db.models.search_result import SearchResult
from app.db.models.search_run import SearchRun
from app.db.models.source_domain import get_or_create_domain
from app.db.models.source_url import SourceUrl
from app.db.models.source_url_discovery import SourceUrlDiscovery
from app.services.search.acquisition_issues import upsert_acquisition_issue
from app.services.search.query_bundle import build_query_bundle
from app.services.search.types import SearchResultItem
from app.services.search.verify_sources import verify_candidate_url
from app.services.fetch.playwright_fetcher import fetch_url_playwright, is_allowlisted

PREFERRED_URL_KEYWORDS = ["termine", "kalender", "veranstaltungen", "programm"]
PREFERRED_DOMAINS = {
    "musenkuss-muenchen.de",
    "muenchen.de",
    "stadt.muenchen.de",
    "veranstaltungen.muenchen.de",
    "muenchner-stadtbibliothek.de",
    "bmw-welt.com",
    "deutsches-museum.de",
}


def _is_preferred_url(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in PREFERRED_URL_KEYWORDS)

def _is_preferred_domain(domain: str) -> bool:
    return domain.lower() in PREFERRED_DOMAINS

logger = logging.getLogger(__name__)


def search_and_seed_sources(
    session,
    provider_search: Callable[[str, str, str, int], list[SearchResultItem]],
    fetcher: Callable[[str, float], tuple[str | None, str | None]],
    now: datetime,
    location: str,
    window_days: int,
    max_results: int = 8,
    query_bundle: list[dict[str, str]] | None = None,
    playwright_fetcher: Callable[[str, float], tuple[str | None, str | None, int | None]] = fetch_url_playwright,
) -> dict[str, object]:
    run = SearchRun(location=location, window_days=window_days)
    session.add(run)
    session.flush()

    queries = query_bundle or build_query_bundle(location=location, window_days=window_days)
    total_results = 0
    candidates: dict[str, SearchResult] = {}

    for query in queries:
        search_query = SearchQuery(
            search_run_id=run.id,
            language=query["language"],
            intent=query["intent"],
            query=query["query"],
        )
        session.add(search_query)
        session.flush()

        results = provider_search(
            query=query["query"],
            language=query["language"],
            location=location,
            max_results=max_results,
        )

        for item in results[:max_results]:
            total_results += 1
            search_result = SearchResult(
                search_query_id=search_query.id,
                rank=item.rank,
                url=item.url,
                title=item.title,
                snippet=item.snippet,
                domain=item.domain,
            )
            session.add(search_result)
            session.flush()
            candidates[item.url] = search_result

    rejected = {
        "blocked_domain": 0,
        "http_blocked": 0,
        "fetch_failed": 0,
        "too_short": 0,
    }
    accepted_soft_signals = {
        "archive_signals": 0,
        "no_date_tokens": 0,
        "js_suspected": 0,
    }
    accepted_urls: list[str] = []
    max_accepted = int(os.getenv("PLANZ_MAX_ACCEPTED_PER_RUN", "25"))
    max_fetched = int(os.getenv("PLANZ_MAX_FETCHED_PER_RUN", "50"))
    caps_hit = {"accepted": False, "fetched": False}
    fetched_count = 0

    for url, search_result in sorted(
        candidates.items(), key=lambda item: _is_preferred_url(item[0]), reverse=True
    ):
        if fetched_count >= max_fetched:
            caps_hit["fetched"] = True
            logger.info("Fetch cap hit (max=%s).", max_fetched)
            break

        ok, reason, canonical, content_length, soft_signal, status = verify_candidate_url(
            url, fetcher=fetcher
        )
        fetched_count += 1

        domain = search_result.domain
        use_playwright = (
            os.getenv("PLANZ_USE_PLAYWRIGHT", "").strip().lower()
            in {"true", "1", "yes"}
        )
        allowlisted_domain = is_allowlisted(domain)

        if not ok and reason == "http_blocked" and use_playwright and allowlisted_domain:
            upsert_acquisition_issue(
                session,
                url=canonical or url,
                domain=domain,
                reason="http_blocked",
                now=now,
                http_status=status,
                content_length=content_length,
                discovered_search_result_id=search_result.id,
            )
            pw_ok, pw_reason, pw_canonical, pw_len, pw_soft, pw_status = verify_candidate_url(
                url, fetcher=playwright_fetcher
            )
            if pw_ok:
                ok, reason, canonical, content_length, soft_signal, status = (
                    pw_ok,
                    pw_reason,
                    pw_canonical,
                    pw_len,
                    pw_soft,
                    pw_status,
                )

        if ok and soft_signal == "js_suspected" and use_playwright and allowlisted_domain:
            upsert_acquisition_issue(
                session,
                url=canonical or url,
                domain=domain,
                reason="js_required",
                now=now,
                http_status=status,
                content_length=content_length,
                discovered_search_result_id=search_result.id,
            )
            pw_ok, pw_reason, pw_canonical, pw_len, pw_soft, pw_status = verify_candidate_url(
                url, fetcher=playwright_fetcher
            )
            if pw_ok:
                ok, reason, canonical, content_length, soft_signal, status = (
                    pw_ok,
                    pw_reason,
                    pw_canonical,
                    pw_len,
                    pw_soft,
                    pw_status,
                )

        if not ok:
            rejected[reason] += 1
            upsert_acquisition_issue(
                session,
                url=canonical or url,
                domain=domain,
                reason=reason,
                now=now,
                http_status=status,
                content_length=content_length,
                discovered_search_result_id=search_result.id,
            )
            continue

        if soft_signal:
            accepted_soft_signals[soft_signal] += 1
            upsert_acquisition_issue(
                session,
                url=canonical or url,
                domain=domain,
                reason=soft_signal,
                now=now,
                http_status=status,
                content_length=content_length,
                discovered_search_result_id=search_result.id,
            )

        domain_row = get_or_create_domain(session, search_result.domain)
        source_url = session.scalar(
            select(SourceUrl).where(SourceUrl.url == canonical)
        )
        if source_url is None:
            source_url = SourceUrl(url=canonical, domain_id=domain_row.id)
            session.add(source_url)
            session.flush()

        session.add(
            SourceUrlDiscovery(
                search_result_id=search_result.id,
                source_url_id=source_url.id,
            )
        )
        accepted_urls.append(canonical)
        if _is_preferred_url(canonical):
            logger.info("Accepted preferred url=%s", canonical)
        else:
            logger.info("Accepted non-preferred url=%s", canonical)

        if len(accepted_urls) >= max_accepted:
            caps_hit["accepted"] = True
            logger.info("Accepted cap hit (max=%s).", max_accepted)
            break

    session.commit()

    return {
        "queries_executed": len(queries),
        "total_results": total_results,
        "unique_candidates": len(candidates),
        "accepted": len(accepted_urls),
        "rejected": rejected,
        "accepted_soft_signals": accepted_soft_signals,
        "accepted_urls": accepted_urls,
        "caps_hit": caps_hit,
    }
