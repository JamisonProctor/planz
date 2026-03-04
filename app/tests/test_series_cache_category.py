"""Test that enrich_with_series_cache propagates category through series to enriched dict."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401
from app.services.extract.series_cache import enrich_with_series_cache
from app.services.llm.summarizer import EventPageSummary


def _make_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


def _session(engine) -> Session:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _noop_fetcher(url: str) -> str:
    return "some page text"


def test_new_series_stores_category() -> None:
    engine = _make_engine()
    session = _session(engine)

    mock_summary = EventPageSummary(
        summary="A theater show for kids.",
        is_paid=False,
        address=None,
        category="theater",
    )
    mock_summarizer = MagicMock(return_value=mock_summary)

    items = [
        {
            "title": "Puppet Show",
            "location": "Stadttheater",
            "detail_url": "https://example.com/puppet",
            "source_url": "https://example.com/listing",
        }
    ]
    now = datetime.now(tz=timezone.utc)
    result = enrich_with_series_cache(
        session=session,
        events=items,
        detail_fetcher=_noop_fetcher,
        now=now,
        summarizer=mock_summarizer,
    )

    assert len(result) == 1
    assert result[0]["category"] == "theater"


def test_cached_series_propagates_category() -> None:
    """Second call with same series key returns cached category without re-fetching."""
    engine = _make_engine()
    session = _session(engine)

    mock_summary = EventPageSummary(
        summary="An outdoor event.",
        is_paid=True,
        address="Somewhere 1",
        category="outdoor",
    )
    mock_summarizer = MagicMock(return_value=mock_summary)

    items = [
        {
            "title": "Park Festival",
            "location": "Englischer Garten",
            "detail_url": "https://example.com/park",
            "source_url": "https://example.com/listing",
        },
        {
            "title": "Park Festival",
            "location": "Englischer Garten",
            "detail_url": "https://example.com/park",
            "source_url": "https://example.com/listing",
        },
    ]
    now = datetime.now(tz=timezone.utc)
    result = enrich_with_series_cache(
        session=session,
        events=items,
        detail_fetcher=_noop_fetcher,
        now=now,
        summarizer=mock_summarizer,
    )

    assert len(result) == 2
    assert result[0]["category"] == "outdoor"
    assert result[1]["category"] == "outdoor"
    # summarizer called only once (second was from cache)
    assert mock_summarizer.call_count == 1


def test_no_category_when_summarizer_returns_none() -> None:
    engine = _make_engine()
    session = _session(engine)

    mock_summarizer = MagicMock(return_value=None)

    items = [
        {
            "title": "Mystery Event",
            "location": "Unknown",
            "detail_url": "https://example.com/mystery",
            "source_url": "https://example.com/listing",
        }
    ]
    now = datetime.now(tz=timezone.utc)
    result = enrich_with_series_cache(
        session=session,
        events=items,
        detail_fetcher=_noop_fetcher,
        now=now,
        summarizer=mock_summarizer,
    )

    assert len(result) == 1
    assert result[0]["category"] is None
