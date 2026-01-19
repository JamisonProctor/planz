from datetime import datetime, timedelta, timezone

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


def test_external_key_upsert_updates_event() -> None:
    session = _make_session()
    source_url = _create_source_url(session, "hash-upsert")
    now = datetime.now(tz=timezone.utc)
    start = (now + timedelta(days=1)).isoformat()
    end = (now + timedelta(days=1, hours=1)).isoformat()

    extracted = [
        {
            "title": "Title",
            "start_time": start,
            "end_time": end,
            "detail_url": "https://example.com/detail",
            "location": "Old",
            "description": "Old desc",
        }
    ]
    store_extracted_events(session, source_url, extracted, now=now)

    extracted[0]["location"] = "New"
    extracted[0]["description"] = "New desc"
    result = store_extracted_events(session, source_url, extracted, now=now, force_extract=True)

    event = session.scalar(select(Event))
    assert result["created"] == 0
    assert result["updated"] == 1
    assert event.location == "New"
    assert event.description == "New desc"
