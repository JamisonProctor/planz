from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.event import Event
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.services.extract.store_extracted_events import store_extracted_events


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _create_source_url(session, content_hash: str) -> SourceUrl:
    domain = SourceDomain(domain="example.com")
    session.add(domain)
    session.flush()
    source_url = SourceUrl(
        url="https://example.com/events",
        domain_id=domain.id,
        fetch_status="ok",
        content_excerpt="content",
        content_hash=content_hash,
    )
    session.add(source_url)
    session.commit()
    session.refresh(source_url)
    return source_url


def test_store_extracted_events_skips_when_hash_unchanged() -> None:
    session = _make_session()
    source_url = _create_source_url(session, content_hash="hash1")
    source_url.last_extracted_hash = "hash1"
    source_url.last_extracted_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    session.commit()

    extracted = [
        {
            "title": "Event",
            "start_time": "2024-01-02T10:00:00+01:00",
            "end_time": "2024-01-02T11:00:00+01:00",
        }
    ]

    created = store_extracted_events(
        session, source_url, extracted, now=datetime.now(tz=timezone.utc)
    )

    assert created == 0
    assert session.scalars(select(Event)).all() == []
    assert source_url.last_extracted_hash == "hash1"


def test_store_extracted_events_creates_rows() -> None:
    session = _make_session()
    source_url = _create_source_url(session, content_hash="hash2")
    now = datetime.now(tz=timezone.utc)

    extracted = [
        {
            "title": "Event A",
            "start_time": "2024-01-02T10:00:00+01:00",
            "end_time": "2024-01-02T11:00:00+01:00",
            "location": "Munich",
        },
        {
            "title": "Event B",
            "start_time": "2024-01-03T10:00:00+01:00",
            "end_time": "2024-01-03T11:30:00+01:00",
            "location": "Munich",
        },
    ]

    created = store_extracted_events(session, source_url, extracted, now=now)

    events = session.scalars(select(Event)).all()
    assert created == 2
    assert len(events) == 2
    assert source_url.last_extracted_hash == "hash2"
    assert source_url.last_extracted_at == now


def test_store_extracted_events_ignores_invalid_items() -> None:
    session = _make_session()
    source_url = _create_source_url(session, content_hash="hash3")

    extracted = [
        {"title": "Missing start"},
        {"start_time": "2024-01-02T10:00:00+01:00"},
        {
            "title": "Valid",
            "start_time": "2024-01-02T10:00:00+01:00",
            "end_time": "2024-01-02T11:00:00+01:00",
        },
    ]

    created = store_extracted_events(
        session, source_url, extracted, now=datetime.now(tz=timezone.utc)
    )

    events = session.scalars(select(Event)).all()
    assert created == 1
    assert len(events) == 1


def test_store_extracted_events_handles_empty_list() -> None:
    session = _make_session()
    source_url = _create_source_url(session, content_hash="hash4")

    created = store_extracted_events(
        session, source_url, [], now=datetime.now(tz=timezone.utc)
    )

    assert created == 0
