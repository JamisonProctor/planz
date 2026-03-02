from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.scripts.extract_muenchen_kinder import (
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
            "is_calendar_candidate": True,
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
            "is_calendar_candidate": True,
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


def test_extract_detail_events_from_listing_expands_visible_date_range_into_daily_rows() -> None:
    listing_html = """
    <html><body>
    <div class="card">
      <div>03 MÄRZ bis 05 MÄRZ</div>
      <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
      <div>Di. 03.03.2026 10:00 - 20:00 Uhr</div>
      <div class="location">Museum Ägyptischer Kunst</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert len(events) == 3
    assert [event["start_time"] for event in events] == [
        "2026-03-03T10:00:00+01:00",
        "2026-03-04T10:00:00+01:00",
        "2026-03-05T10:00:00+01:00",
    ]
    assert [event["end_time"] for event in events] == [
        "2026-03-03T20:00:00+01:00",
        "2026-03-04T20:00:00+01:00",
        "2026-03-05T20:00:00+01:00",
    ]
    assert all(
        event["location"] == "Museum Ägyptischer Kunst"
        for event in events
    )


def test_extract_detail_events_from_listing_uses_ticket_only_rows_without_detail_link() -> None:
    listing_html = """
    <html><body>
    <li class="m-listing__list-item">
      <div class="m-event-list-item">
        <div class="m-event-list-item__grid">
          <div class="m-event-list-item__date">
            <div class="m-date-range">
              <time class="m-date-range__item" itemprop="startDate" datetime="2026-03-06T12:00:00Z"></time>
              <div class="m-date-range__label"><span>bis</span></div>
              <time class="m-date-range__item" itemprop="endDate" datetime="2026-03-06T12:00:00Z"></time>
            </div>
          </div>
          <div class="m-event-list-item__body">
            <h3 class="m-event-list-item__headline"><span>AnimaCzech: Kurzfilme aus Tschechien</span></h3>
            <p class="m-event-list-item__detail">
              <time datetime="06.03.2026 - 15:00:00">Fr. 06.03.2026 15:00</time>
              -
              <time datetime="06.03.2026 - 16:30:00">16:30 Uhr</time>
            </p>
            <p class="m-event-list-item__detail" itemprop="location">Gasteig HP8</p>
          </div>
          <div class="m-event-list-item__meta">
            <a href="https://www.muenchenticket.de/event/grosses-kinderkino-35968/441877?campaign=muenchen">
              <span>Tickets</span>
            </a>
          </div>
        </div>
      </div>
    </li>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert events == [
        {
            "title": "🎟 AnimaCzech: Kurzfilme aus Tschechien",
            "start_time": "2026-03-06T15:00:00+01:00",
            "end_time": "2026-03-06T16:30:00+01:00",
            "raw_schedule": "Fr. 06.03.2026 15:00 - 16:30 Uhr",
            "source_url": "https://www.muenchenticket.de/event/grosses-kinderkino-35968/441877?campaign=muenchen",
            "ticket_url": "https://www.muenchenticket.de/event/grosses-kinderkino-35968/441877?campaign=muenchen",
            "location": "Gasteig HP8",
            "is_calendar_candidate": True,
        }
    ]


def test_extract_detail_events_date_range_marks_weekdays_as_non_candidates() -> None:
    """Range-expanded events must set is_calendar_candidate based on weekend/holiday rules."""
    listing_html = """
    <html><body>
    <div class="card">
      <div>05 MÄRZ bis 09 MÄRZ</div>
      <a href="/veranstaltungen/ausstellungen/kinder/some-event">Some Exhibition</a>
      <div>Do. 05.03.2026 10:00 - 17:00 Uhr</div>
      <div class="location">Museum</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    # Mar 5=Thu, Mar 6=Fri, Mar 7=Sat, Mar 8=Sun, Mar 9=Mon
    assert len(events) == 5
    assert [e["start_time"][:10] for e in events] == [
        "2026-03-05", "2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09"
    ]
    assert [e.get("is_calendar_candidate") for e in events] == [
        False, False, True, True, False
    ]


def test_extract_detail_events_single_occurrence_is_always_candidate() -> None:
    """Single-occurrence events (no date range) must always be calendar candidates."""
    listing_html = """
    <html><body>
    <div class="card">
      <a href="/veranstaltungen/ausstellungen/kinder/some-event">Some Event</a>
      <div>Mi. 04.03.2026 10:00 - 12:00 Uhr</div>
    </div>
    </body></html>
    """

    events = extract_detail_events_from_listing(
        listing_html=listing_html,
        listing_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert len(events) == 1
    assert events[0].get("is_calendar_candidate", True) is True


def test_resolve_sync_limit_uses_max_events_for_debug_runs() -> None:
    assert _resolve_sync_limit(None) == 200
    assert _resolve_sync_limit(3) == 3
