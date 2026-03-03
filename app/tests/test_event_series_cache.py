from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.event_series import EventSeries
from app.services.extract.series_cache import enrich_with_series_cache


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _identity_summarizer(text: str) -> str | None:
    """Fake summarizer that returns the text unchanged — no LLM call."""
    return text


def test_enrich_with_series_cache_fetches_once() -> None:
    session = _make_session()

    calls = {"count": 0}

    def fetch_detail(detail_url: str) -> str:
        calls["count"] += 1
        return "Detailed description"

    events = [
        {"title": "Show", "location": "Hall", "detail_url": "https://example.com/detail", "start_time": datetime.now(tz=timezone.utc)},
        {"title": "Show", "location": "Hall", "detail_url": "https://example.com/detail", "start_time": datetime.now(tz=timezone.utc)},
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=_identity_summarizer,
    )

    descriptions = {e["description"] for e in enriched}
    assert descriptions == {"Detailed description"}
    assert calls["count"] == 1
    cached = session.scalar(select(EventSeries))
    assert cached is not None
    assert cached.detail_url == "https://example.com/detail"


def test_enrich_with_series_cache_strips_html_from_detail_description() -> None:
    session = _make_session()

    def fetch_detail(detail_url: str) -> str:
        return "<html><body><h1>Show</h1><p>Family friendly fun.</p></body></html>"

    events = [
        {
            "title": "Show",
            "location": "Hall",
            "detail_url": "https://example.com/detail",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=_identity_summarizer,
    )

    assert enriched[0]["description"] == "Show Family friendly fun."


def test_enrich_sets_llm_summary_as_description() -> None:
    session = _make_session()

    def fetch_detail(detail_url: str) -> str:
        return "Kinderfest page content"

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> str | None:
        summarizer_calls["count"] += 1
        return "A great kids festival for ages 4-10."

    events = [
        {
            "title": "Kinderfest",
            "location": "Park",
            "detail_url": "https://example.com/kinderfest",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["description"] == "A great kids festival for ages 4-10."
    assert summarizer_calls["count"] == 1


def test_enrich_uses_cached_description_without_calling_summarizer() -> None:
    session = _make_session()

    # Pre-populate the series cache
    existing = EventSeries(
        series_key="https://example.com/cached",
        detail_url="https://example.com/cached",
        title="Cached Event",
        venue="Somewhere",
        description="Cached summary from a previous run.",
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> str | None:
        summarizer_calls["count"] += 1
        return "Should not be called"

    def fetch_detail(detail_url: str) -> str:
        return "Should not be called either"

    events = [
        {
            "title": "Cached Event",
            "location": "Somewhere",
            "detail_url": "https://example.com/cached",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["description"] == "Cached summary from a previous run."
    assert summarizer_calls["count"] == 0


def test_enrich_skips_description_when_summarizer_returns_none() -> None:
    session = _make_session()

    def fetch_detail(detail_url: str) -> str:
        return "Some page text"

    def none_summarizer(text: str) -> str | None:
        return None

    events = [
        {
            "title": "Event",
            "location": "Venue",
            "detail_url": "https://example.com/event",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=none_summarizer,
    )

    assert "description" not in enriched[0]


def test_enrich_fills_missing_description_on_cached_series_with_detail_url() -> None:
    """If an EventSeries already exists but has no description, LLM should be called to fill it in."""
    session = _make_session()

    # Pre-populate series with detail_url but no description (as if created by old code)
    existing = EventSeries(
        series_key="https://example.com/show",
        detail_url="https://example.com/show",
        title="Some Show",
        venue="Theater",
        description=None,
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> str | None:
        summarizer_calls["count"] += 1
        return "A great show for families."

    def fetch_detail(url: str) -> str:
        return "Show page content"

    events = [
        {
            "title": "Some Show",
            "location": "Theater",
            "detail_url": "https://example.com/show",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["description"] == "A great show for families."
    assert summarizer_calls["count"] == 1
    # Description should now be persisted on the series row
    session.refresh(existing)
    assert existing.description == "A great show for families."


def test_enrich_sets_llm_summary_from_source_url_when_no_detail_url() -> None:
    """Ticket-only events with no detail_url should be summarized using their source_url."""
    session = _make_session()

    fetched_urls = []

    def fetch_detail(url: str) -> str:
        fetched_urls.append(url)
        return "Ticket page content about the show"

    def fake_summarizer(text: str) -> str | None:
        return "A fun show for kids aged 4-8."

    events = [
        {
            "title": "🎟 Die kleine Hexe",
            "location": "Theater",
            "source_url": "https://www.muenchenticket.de/event/hexe/440797",
            "start_time": datetime.now(tz=timezone.utc),
            # No detail_url
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["description"] == "A fun show for kids aged 4-8."
    assert fetched_urls == ["https://www.muenchenticket.de/event/hexe/440797"]


def test_enrich_fills_missing_description_on_cached_series_without_detail_url() -> None:
    """Cached ticket-only series with no description should use source_url to fill it in."""
    session = _make_session()

    # Pre-populate series with no detail_url and no description
    existing = EventSeries(
        series_key="www.muenchenticket.de:🎟 die kleine hexe:theater",
        detail_url=None,
        title="🎟 Die kleine Hexe",
        venue="Theater",
        description=None,
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> str | None:
        summarizer_calls["count"] += 1
        return "A spooky witch story for children."

    def fetch_detail(url: str) -> str:
        return "Ticket page content"

    events = [
        {
            "title": "🎟 Die kleine Hexe",
            "location": "Theater",
            "source_url": "https://www.muenchenticket.de/event/hexe/440797",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["description"] == "A spooky witch story for children."
    assert summarizer_calls["count"] == 1
    session.refresh(existing)
    assert existing.description == "A spooky witch story for children."
