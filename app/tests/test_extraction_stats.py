from datetime import datetime, timezone

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


def _create_source(session, content_hash: str, last_hash: str | None = None) -> SourceUrl:
    domain = SourceDomain(domain="example.com", is_allowed=True)
    session.add(domain)
    session.flush()
    source_url = SourceUrl(
        url="https://example.com/events",
        domain_id=domain.id,
        fetch_status="ok",
        content_excerpt="content",
        content_hash=content_hash,
        last_extracted_hash=last_hash,
    )
    session.add(source_url)
    session.commit()
    session.refresh(source_url)
    return source_url


def test_extraction_sets_empty_status_when_no_events_returned() -> None:
    session = _make_session()
    source_url = _create_source(session, content_hash="hash1", last_hash="old")

    def extractor(text: str, source_url: str):
        return []

    stats = extract_and_store_for_sources(
        session, extractor=extractor, now=datetime.now(tz=timezone.utc)
    )

    refreshed = session.get(SourceUrl, source_url.id)
    assert refreshed.last_extraction_status == "empty"
    assert refreshed.last_extraction_count == 0
    assert refreshed.last_extraction_error is None
    assert stats["sources_empty_extraction"] == 1


def test_extraction_sets_error_status_on_exception() -> None:
    session = _make_session()
    source_url = _create_source(session, content_hash="hash2", last_hash="old")

    def extractor(text: str, source_url: str):
        raise RuntimeError("boom")

    stats = extract_and_store_for_sources(
        session, extractor=extractor, now=datetime.now(tz=timezone.utc)
    )

    refreshed = session.get(SourceUrl, source_url.id)
    assert refreshed.last_extraction_status == "error"
    assert refreshed.last_extraction_error is not None
    assert stats["sources_error_extraction"] == 1


def test_extraction_sets_ok_and_count_on_success() -> None:
    session = _make_session()
    source_url = _create_source(session, content_hash="hash3", last_hash="old")

    def extractor(text: str, source_url: str):
        return [
            {"title": "A", "start_time": "2024-01-02T10:00:00+01:00"},
            {"title": "B", "start_time": "2024-01-03T10:00:00+01:00"},
        ]

    stats = extract_and_store_for_sources(
        session, extractor=extractor, now=datetime.now(tz=timezone.utc)
    )

    refreshed = session.get(SourceUrl, source_url.id)
    events = session.scalars(select(Event)).all()
    assert refreshed.last_extraction_status == "ok"
    assert refreshed.last_extraction_count == 2
    assert refreshed.last_extraction_error is None
    assert len(events) == 2
    assert stats["events_created_total"] == 2
