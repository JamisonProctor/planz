from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.event_series import EventSeries
from app.services.extract.series_cache import enrich_with_series_cache
from app.services.llm.summarizer import EventPageSummary


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _identity_summarizer(text: str) -> EventPageSummary | None:
    """Fake summarizer that returns the text as summary — no LLM call."""
    return EventPageSummary(summary=text, is_paid=False, address=None)


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

    def fake_summarizer(text: str) -> EventPageSummary | None:
        summarizer_calls["count"] += 1
        return EventPageSummary(summary="A great kids festival for ages 4-10.", is_paid=False, address=None)

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

    # Pre-populate the series cache with all fields filled
    existing = EventSeries(
        series_key="https://example.com/cached",
        detail_url="https://example.com/cached",
        title="Cached Event",
        venue="Somewhere",
        description="Cached summary from a previous run.",
        venue_address="Cached Strasse 1, 80538 München",
        is_paid=False,
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> EventPageSummary | None:
        summarizer_calls["count"] += 1
        return EventPageSummary(summary="Should not be called", is_paid=False, address=None)

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

    def none_summarizer(text: str) -> EventPageSummary | None:
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
        venue_address=None,
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> EventPageSummary | None:
        summarizer_calls["count"] += 1
        return EventPageSummary(summary="A great show for families.", is_paid=False, address=None)

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

    def fake_summarizer(text: str) -> EventPageSummary | None:
        return EventPageSummary(summary="A fun show for kids aged 4-8.", is_paid=True, address=None)

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
        venue_address=None,
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> EventPageSummary | None:
        summarizer_calls["count"] += 1
        return EventPageSummary(summary="A spooky witch story for children.", is_paid=True, address=None)

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


def test_enrich_propagates_is_paid_to_event_dict() -> None:
    """is_paid=True on a series must appear in the enriched event dict."""
    session = _make_session()

    def fetch_detail(url: str) -> str:
        return "Show page content"

    def fake_summarizer(text: str) -> EventPageSummary | None:
        return EventPageSummary(summary="A paid show.", is_paid=True, address=None)

    events = [
        {
            "title": "Paid Show",
            "location": "Theater",
            "detail_url": "https://example.com/paid",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["is_paid"] is True


def test_enrich_propagates_venue_address_to_event_dict() -> None:
    """venue_address from the series must appear in the enriched event dict."""
    session = _make_session()

    def fetch_detail(url: str) -> str:
        return "Museum page content"

    def fake_summarizer(text: str) -> EventPageSummary | None:
        return EventPageSummary(
            summary="A museum exhibit.", is_paid=False, address="Museumstrasse 1, 80538 München"
        )

    events = [
        {
            "title": "Museum Exhibit",
            "location": "Museum",
            "detail_url": "https://example.com/museum",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert enriched[0]["venue_address"] == "Museumstrasse 1, 80538 München"


def test_enrich_fills_missing_venue_address_on_cached_series() -> None:
    """Existing series with description but no venue_address should trigger re-summarize."""
    session = _make_session()

    # Pre-populate series with description but no venue_address (post-migration state)
    existing = EventSeries(
        series_key="https://example.com/museum",
        detail_url="https://example.com/museum",
        title="Museum Exhibit",
        venue="Museum",
        description="An existing cached description.",
        venue_address=None,
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(existing)
    session.commit()

    summarizer_calls = {"count": 0}

    def fake_summarizer(text: str) -> EventPageSummary | None:
        summarizer_calls["count"] += 1
        return EventPageSummary(
            summary="Updated summary.", is_paid=False, address="Maximilianstrasse 5, 80538 München"
        )

    def fetch_detail(url: str) -> str:
        return "Museum page content"

    events = [
        {
            "title": "Museum Exhibit",
            "location": "Museum",
            "detail_url": "https://example.com/museum",
            "start_time": datetime.now(tz=timezone.utc),
        }
    ]

    enriched = enrich_with_series_cache(
        session, events, fetch_detail, now=datetime.now(tz=timezone.utc),
        summarizer=fake_summarizer,
    )

    assert summarizer_calls["count"] == 1
    assert enriched[0]["venue_address"] == "Maximilianstrasse 5, 80538 München"
    session.refresh(existing)
    assert existing.venue_address == "Maximilianstrasse 5, 80538 München"
