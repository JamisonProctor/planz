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
        last_extracted_hash="hash1",
    )
    session.add(source_url)
    session.commit()
    session.refresh(source_url)
    return source_url


def test_force_extract_overrides_hash_skip(monkeypatch) -> None:
    session = _make_session()
    source_url = _create_source(session)

    monkeypatch.setenv("PLANZ_FORCE_EXTRACT", "true")

    def extractor(text: str, source_url: str):
        return [
            {"title": "A", "start_time": "2024-01-02T10:00:00+01:00"}
        ]

    stats = extract_and_store_for_sources(
        session, extractor=extractor, now=datetime.now(tz=timezone.utc)
    )

    events = session.scalars(select(Event)).all()
    refreshed = session.get(SourceUrl, source_url.id)
    assert len(events) == 1
    assert stats["events_created_total"] == 1
    assert refreshed.last_extracted_hash == "hash1"


def test_force_extract_disabled_keeps_idempotency(monkeypatch) -> None:
    session = _make_session()
    _create_source(session)

    monkeypatch.delenv("PLANZ_FORCE_EXTRACT", raising=False)

    def extractor(text: str, source_url: str):
        return [
            {"title": "A", "start_time": "2024-01-02T10:00:00+01:00"}
        ]

    stats = extract_and_store_for_sources(
        session, extractor=extractor, now=datetime.now(tz=timezone.utc)
    )

    events = session.scalars(select(Event)).all()
    assert len(events) == 0
    assert stats["events_created_total"] == 0
