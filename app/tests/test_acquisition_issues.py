from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.acquisition_issue import AcquisitionIssue
from app.services.search.seed_sources import search_and_seed_sources
from app.services.search.types import SearchResultItem


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_rejected_candidate_creates_acquisition_issue() -> None:
    session = _make_session()

    def provider_search(query: str, language: str, location: str, max_results: int):
        return [
            SearchResultItem(
                url="https://example.com/bad",
                title="Bad",
                snippet="snippet",
                rank=1,
                domain="example.com",
            )
        ]

    def fetcher(url: str, timeout: float = 5.0):
        return None, "404", 404

    stats = search_and_seed_sources(
        session,
        provider_search=provider_search,
        fetcher=fetcher,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        location="Munich, Germany",
        window_days=30,
        query_bundle=[{"language": "en", "intent": "kids", "query": "kids"}],
    )

    issue = session.scalar(select(AcquisitionIssue))
    assert issue is not None
    assert issue.reason == "http_blocked"
    assert stats["rejected"]["http_blocked"] == 1


def test_acquisition_issue_upsert_updates_last_seen() -> None:
    session = _make_session()

    def provider_search(query: str, language: str, location: str, max_results: int):
        return [
            SearchResultItem(
                url="https://example.com/bad",
                title="Bad",
                snippet="snippet",
                rank=1,
                domain="example.com",
            )
        ]

    def fetcher(url: str, timeout: float = 5.0):
        return None, "404", 404

    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(days=1)

    search_and_seed_sources(
        session,
        provider_search=provider_search,
        fetcher=fetcher,
        now=first,
        location="Munich, Germany",
        window_days=30,
        query_bundle=[{"language": "en", "intent": "kids", "query": "kids"}],
    )

    search_and_seed_sources(
        session,
        provider_search=provider_search,
        fetcher=fetcher,
        now=second,
        location="Munich, Germany",
        window_days=30,
        query_bundle=[{"language": "en", "intent": "kids", "query": "kids"}],
    )

    issue = session.scalar(select(AcquisitionIssue))
    assert issue is not None
    assert issue.last_seen_at >= first
