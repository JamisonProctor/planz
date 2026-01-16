from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.event import Event
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.services.extract.extract_and_store import extract_and_store_for_sources


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _create_source(session) -> SourceUrl:
    domain = SourceDomain(domain="example.com", is_allowed=True)
    session.add(domain)
    session.flush()
    source_url = SourceUrl(
        url="https://example.com/events",
        domain_id=domain.id,
        fetch_status="ok",
        content_excerpt="content",
        content_hash="hash1",
        last_extracted_hash="old",
    )
    session.add(source_url)
    session.commit()
    session.refresh(source_url)
    return source_url


def test_past_events_are_discarded_and_marked_past_only() -> None:
    session = _make_session()
    source_url = _create_source(session)
    now = datetime.now(tz=timezone.utc)
    past = (now - timedelta(days=2)).isoformat()

    def extractor(text: str, source_url: str):
        return [{"title": "Past", "start_time": past, "end_time": past}]

    stats = extract_and_store_for_sources(session, extractor=extractor, now=now)

    refreshed = session.get(SourceUrl, source_url.id)
    events = session.scalars(select(Event)).all()
    assert len(events) == 0
    assert refreshed.last_extraction_status == "past_only"
    assert refreshed.last_extraction_count == 0
    assert stats["sources_past_only"] == 1


def test_weekend_slicing_creates_saturday_sunday_only() -> None:
    session = _make_session()
    _create_source(session)
    now = datetime(2026, 1, 16, 12, 0, tzinfo=timezone.utc)

    def extractor(text: str, source_url: str):
        return [
            {
                "title": "Weekend Festival",
                "start_time": "2026-01-16T10:00:00+01:00",  # Friday
                "end_time": "2026-01-18T18:00:00+01:00",    # Sunday
            }
        ]

    stats = extract_and_store_for_sources(session, extractor=extractor, now=now)

    events = session.scalars(select(Event)).all()
    titles = {event.title for event in events}
    assert stats["events_created_total"] == 2
    assert len(events) == 2
    assert "Weekend Festival (Saturday)" in titles
    assert "Weekend Festival (Sunday)" in titles


def test_multi_day_without_weekend_creates_no_events() -> None:
    session = _make_session()
    _create_source(session)
    now = datetime(2026, 1, 13, 12, 0, tzinfo=timezone.utc)

    def extractor(text: str, source_url: str):
        return [
            {
                "title": "Weekday Workshop",
                "start_time": "2026-01-14T10:00:00+01:00",  # Wednesday
                "end_time": "2026-01-15T18:00:00+01:00",    # Thursday
            }
        ]

    stats = extract_and_store_for_sources(session, extractor=extractor, now=now)

    events = session.scalars(select(Event)).all()
    assert len(events) == 0
    assert stats["events_created_total"] == 0
