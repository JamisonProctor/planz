from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.scripts.extract_muenchen_kinder import extract_detail_events_from_listing, prepare_source_url


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


def test_extract_detail_events_from_listing_fetches_each_detail_page() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
      <div class="address">Museumstrasse 1</div>
    </div>
    </body></html>
    """
    fetch_calls: list[str] = []
    extract_calls: list[str] = []

    def fetcher(url: str):
        fetch_calls.append(url)
        return ("detail content", None, 200)

    def extractor(text: str, source_url: str):
        extract_calls.append(source_url)
        return [{"title": "Kindheit am Nil", "start_time": "2026-03-07T10:00:00+01:00"}]

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
        fetcher=fetcher,
        extractor=extractor,
    )

    assert fetch_calls == [
        "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum"
    ]
    assert extract_calls == [
        "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum"
    ]
    assert events == [
        {
            "title": "Kindheit am Nil",
            "start_time": "2026-03-07T10:00:00+01:00",
            "detail_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "source_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "location": "Museumstrasse 1",
        }
    ]


def test_extract_detail_events_from_listing_passes_listing_and_detail_content_to_extractor() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
    </div>
    <div class="card">
      <a href="/not-an-event">Other Event</a>
    </div>
    </body></html>
    """
    seen_texts: list[str] = []

    def fetcher(url: str):
        return ("DETAIL DATE: 7 March, Museumstrasse 1", None, 200)

    def extractor(text: str, source_url: str):
        seen_texts.append(text)
        return [{"title": "Kindheit am Nil", "start_time": "2026-03-07T10:00:00+01:00"}]

    extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
        fetcher=fetcher,
        extractor=extractor,
    )

    assert len(seen_texts) == 1
    assert "Kindheit am Nil" in seen_texts[0]
    assert "DETAIL DATE: 7 March, Museumstrasse 1" in seen_texts[0]
    assert "Other Event" not in seen_texts[0]


def test_extract_detail_events_from_listing_uses_ticket_url_and_marks_title() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
      <a class="ticket-icon" href="https://tickets.example.com/kindheit-am-nil" title="Tickets">Buy</a>
      <div class="address">Museumstrasse 1</div>
    </div>
    </body></html>
    """

    def fetcher(url: str):
        return ("detail content", None, 200)

    def extractor(text: str, source_url: str):
        return [{"title": "Kindheit am Nil", "start_time": "2026-03-07T10:00:00+01:00"}]

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
        fetcher=fetcher,
        extractor=extractor,
    )

    assert events == [
        {
            "title": "🎟 Kindheit am Nil",
            "start_time": "2026-03-07T10:00:00+01:00",
            "detail_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "source_url": "https://tickets.example.com/kindheit-am-nil",
            "ticket_url": "https://tickets.example.com/kindheit-am-nil",
            "location": "Museumstrasse 1",
        }
    ]
