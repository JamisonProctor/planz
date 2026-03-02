from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.scripts.extract_muenchen_kinder import (
    _build_detail_summary_fetcher,
    _resolve_sync_limit,
    extract_detail_events_from_listing,
    prepare_source_url,
)


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_prepare_source_url_reuses_existing() -> None:
    session = _make_session()
    domain = SourceDomain(domain="example.com")
    session.add(domain)
    session.flush()
    existing = SourceUrl(url="https://example.com/list", domain_id=domain.id)
    session.add(existing)
    session.commit()

    source_url = prepare_source_url(session, url="https://example.com/list", domain_row=domain)
    assert source_url.id == existing.id
    assert session.scalar(select(SourceUrl)).id == existing.id


def test_extract_detail_events_from_listing_uses_listing_rows_as_canonical_events() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
      <div>Fr. 07.03.2026 10:00 - 12:00 Uhr</div>
      <div class="address">Museumstrasse 1</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert events == [
        {
            "title": "Kindheit am Nil",
            "start_time": "2026-03-07T10:00:00+01:00",
            "end_time": "2026-03-07T12:00:00+01:00",
            "raw_schedule": "Fr. 07.03.2026 10:00 - 12:00 Uhr",
            "detail_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "source_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "location": "Museumstrasse 1",
        }
    ]


def test_extract_detail_events_from_listing_skips_rows_without_structured_schedule() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
      <div>Fr. 07.03.2026 10:00 - 12:00 Uhr</div>
    </div>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/without-schedule">No Schedule Yet</a>
      <div class="address">Museumstrasse 2</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert [event["title"] for event in events] == ["Kindheit am Nil"]


def test_extract_detail_events_from_listing_uses_ticket_url_and_marks_title() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
      <div>Fr. 07.03.2026 10:00 - 12:00 Uhr</div>
      <a class="ticket-icon" href="https://tickets.example.com/kindheit-am-nil" title="Tickets">Buy</a>
      <div class="address">Museumstrasse 1</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert events == [
        {
            "title": "🎟 Kindheit am Nil",
            "start_time": "2026-03-07T10:00:00+01:00",
            "end_time": "2026-03-07T12:00:00+01:00",
            "raw_schedule": "Fr. 07.03.2026 10:00 - 12:00 Uhr",
            "detail_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "source_url": "https://tickets.example.com/kindheit-am-nil",
            "ticket_url": "https://tickets.example.com/kindheit-am-nil",
            "location": "Museumstrasse 1",
        }
    ]


def test_extract_detail_events_from_listing_respects_max_items() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/one">One</a>
      <div>Fr. 07.03.2026 10:00 - 12:00 Uhr</div>
    </div>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/two">Two</a>
      <div>Sa. 08.03.2026 10:00 - 12:00 Uhr</div>
    </div>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/three">Three</a>
      <div>So. 09.03.2026 10:00 - 12:00 Uhr</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
        max_items=2,
    )

    assert len(events) == 2
    assert events[0]["title"] == "One"
    assert events[1]["title"] == "Two"


def test_build_detail_summary_fetcher_returns_summary_with_cost() -> None:
    fetch_calls: list[str] = []
    summarize_calls: list[tuple[str, str]] = []

    def fetcher(url: str):
        fetch_calls.append(url)
        return (
            "<html><body><h1>Der Gasteig brummt!</h1><p>Tickets fuer nur 3 Euro.</p></body></html>",
            None,
            200,
        )

    def summarizer(text: str, source_url: str):
        summarize_calls.append((text, source_url))
        return {"summary": "Musiktage fuer Kinder zum Mitmachen.", "cost": "3 Euro"}

    fetch_detail_summary = _build_detail_summary_fetcher(fetcher, summarizer)

    summary = fetch_detail_summary("https://www.muenchen.de/veranstaltungen/kinder/der-gasteig-brummt")

    assert fetch_calls == ["https://www.muenchen.de/veranstaltungen/kinder/der-gasteig-brummt"]
    assert summarize_calls == [
        (
            "Der Gasteig brummt! Tickets fuer nur 3 Euro.",
            "https://www.muenchen.de/veranstaltungen/kinder/der-gasteig-brummt",
        )
    ]
    assert summary == "Musiktage fuer Kinder zum Mitmachen.\n\nCost: 3 Euro"


def test_resolve_sync_limit_uses_max_events_for_debug_runs() -> None:
    assert _resolve_sync_limit(None) == 200
    assert _resolve_sync_limit(3) == 3
