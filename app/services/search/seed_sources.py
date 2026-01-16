from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy import select

from app.db.models.search_query import SearchQuery
from app.db.models.search_result import SearchResult
from app.db.models.search_run import SearchRun
from app.db.models.source_domain import get_or_create_domain
from app.db.models.source_url import SourceUrl
from app.db.models.source_url_discovery import SourceUrlDiscovery
from app.services.search.query_bundle import build_query_bundle
from app.services.search.types import SearchResultItem
from app.services.search.verify_sources import verify_candidate_url

PREFERRED_URL_KEYWORDS = ["termine", "kalender", "veranstaltungen", "programm"]


def _is_preferred_url(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in PREFERRED_URL_KEYWORDS)

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
    }
    accepted_urls: list[str] = []

    for url, search_result in sorted(
        candidates.items(), key=lambda item: _is_preferred_url(item[0]), reverse=True
    ):
        ok, reason, canonical = verify_candidate_url(url, fetcher=fetcher)
        if not ok:
            rejected[reason] += 1
            if reason == "archive_signals":
                logger.info("Rejected archive/past url=%s", url)
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
