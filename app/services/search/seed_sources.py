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

PREFERRED_URL_KEYWORDS = ["termine", "kalender", "veranstaltungen", "programm"]
AGGREGATOR_DOMAINS = {
    "termine.de",
    "eventfrog.de",
    "allevents.in",
    "feverup.com",
    "rausgegangen.de",
}
PREFERRED_DOMAINS = {
    "musenkuss-muenchen.de",
    "muenchen.de",
    "stadt.muenchen.de",
    "veranstaltungen.muenchen.de",
    "muenchner-stadtbibliothek.de",
    "bmw-welt.com",
    "deutsches-museum.de",
}
AGGREGATOR_CAP = 2


def _is_preferred_url(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in PREFERRED_URL_KEYWORDS)

def _is_aggregator_domain(domain: str) -> bool:
    return domain.lower() in AGGREGATOR_DOMAINS


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
        "fetch_failed": 0,
        "too_short": 0,
        "no_date_tokens": 0,
        "archive_signals": 0,
        "js_suspected": 0,
        "past_only": 0,
        "aggregator_blocked": 0,
        "aggregator_capped": 0,
    }
    accepted_urls: list[str] = []
    aggregator_accepted = 0
    allow_aggregators = os.getenv("PLANZ_ALLOW_AGGREGATORS", "false").strip().lower() in {
        "true",
        "1",
        "yes",
    }

    for url, search_result in sorted(
        candidates.items(), key=lambda item: _is_preferred_url(item[0]), reverse=True
    ):
        domain = search_result.domain
        if _is_aggregator_domain(domain) and not _is_preferred_domain(domain):
            if not allow_aggregators:
                rejected["aggregator_blocked"] += 1
                upsert_acquisition_issue(
                    session,
                    url=url,
                    domain=domain,
                    reason="aggregator_blocked",
                    now=now,
                    discovered_search_result_id=search_result.id,
                )
                continue
            if aggregator_accepted >= AGGREGATOR_CAP:
                rejected["aggregator_capped"] += 1
                upsert_acquisition_issue(
                    session,
                    url=url,
                    domain=domain,
                    reason="aggregator_capped",
                    now=now,
                    discovered_search_result_id=search_result.id,
                )
                continue

        ok, reason, canonical, content_length = verify_candidate_url(
            url,
            fetcher=fetcher,
            now=now,
            window_days=window_days,
        )
        if not ok:
            rejected[reason] += 1
            if reason == "archive_signals":
                logger.info("Rejected archive/past url=%s", url)
            upsert_acquisition_issue(
                session,
                url=canonical or url,
                domain=search_result.domain,
                reason=reason,
                now=now,
                content_length=content_length,
                discovered_search_result_id=search_result.id,
            )
            continue

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
        if _is_aggregator_domain(domain) and not _is_preferred_domain(domain):
            aggregator_accepted += 1
        if _is_preferred_url(canonical):
            logger.info("Accepted preferred url=%s", canonical)
        else:
            logger.info("Accepted non-preferred url=%s", canonical)

    session.commit()

    return {
        "queries_executed": len(queries),
        "total_results": total_results,
        "unique_candidates": len(candidates),
        "accepted": len(accepted_urls),
        "rejected": rejected,
        "accepted_urls": accepted_urls,
    }
