from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.search_query import SearchQuery
from app.db.models.search_result import SearchResult
from app.db.models.search_run import SearchRun
from app.db.models.source_url import SourceUrl
from app.services.search.seed_sources import search_and_seed_sources
from app.services.search.types import SearchResultItem


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_search_seeding_verifies_and_persists() -> None:
    session = _make_session()

    def provider_search(query: str, language: str, location: str, max_results: int):
        return [
            SearchResultItem(
                url="https://example.com/good",
                title="Good",
                snippet="snippet",
                rank=1,
                domain="example.com",
            ),
            SearchResultItem(
                url="https://example.com/nodate",
                title="NoDate",
                snippet="snippet",
                rank=2,
                domain="example.com",
            ),
            SearchResultItem(
                url="https://example.com/archive",
                title="Archive",
                snippet="snippet",
                rank=3,
                domain="example.com",
            ),
        ]

    def fetcher(url: str, timeout: float = 5.0):
        if url.endswith("/good"):
            return "Event on 2026-01-10 " * 200, None
        if url.endswith("/nodate"):
            return "No dates here " * 200, None
        return "Archiv 2023 events " * 200, None

    stats = search_and_seed_sources(
        session,
        provider_search=provider_search,
        fetcher=fetcher,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        location="Munich, Germany",
        window_days=30,
        query_bundle=[
            {
                "language": "en",
                "intent": "kids_free_weekend",
                "query": "kids events Munich",
            }
        ],
    )

    urls = session.scalars(select(SourceUrl)).all()
    runs = session.scalars(select(SearchRun)).all()
    queries = session.scalars(select(SearchQuery)).all()
    results = session.scalars(select(SearchResult)).all()

    assert len(runs) == 1
    assert len(queries) == 1
    assert len(results) == 3
    assert len(urls) == 1
    assert stats["accepted"] == 1
    assert stats["rejected"]["no_date_tokens"] == 1
    assert stats["rejected"]["archive_signals"] == 1
