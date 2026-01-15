from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.urls import canonicalize_url
from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.services.discovery.store_sources import store_discovered_sources


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_store_sources_idempotent_updates_last_seen() -> None:
    session = _make_session()
    sources = [
        {
            "url": "https://example.com/events",
            "name": "Example Events",
            "type": "museum",
            "reason": "Kids programming",
        },
        {
            "url": "https://muenchen.de/kinder",
            "name": "City Portal",
            "type": "city_portal",
            "reason": "Official listing",
        },
    ]

    now = datetime.now(tz=timezone.utc)
    result_first = store_discovered_sources(session, sources, now)

    assert result_first["new_domains"] == 2
    assert result_first["new_urls"] == 2
    assert result_first["updated_urls"] == 0
    assert len(result_first["active_urls"]) == 2

    stored_url = session.scalar(
        select(SourceUrl).where(SourceUrl.url == canonicalize_url(sources[0]["url"]))
    )
    assert stored_url is not None
    first_seen = stored_url.last_seen_at

    later = now + timedelta(minutes=5)
    result_second = store_discovered_sources(session, sources, later)

    assert result_second["new_domains"] == 0
    assert result_second["new_urls"] == 0
    assert result_second["updated_urls"] == 2

    stored_url = session.scalar(
        select(SourceUrl).where(SourceUrl.url == canonicalize_url(sources[0]["url"]))
    )
    assert stored_url is not None
    assert stored_url.last_seen_at >= first_seen

    domains = session.scalars(select(SourceDomain)).all()
    urls = session.scalars(select(SourceUrl)).all()
    assert len(domains) == 2
    assert len(urls) == 2


def test_store_sources_respects_kill_switch() -> None:
    session = _make_session()
    domain = SourceDomain(domain="example.com", is_allowed=False)
    session.add(domain)
    session.commit()

    sources = [
        {
            "url": "https://example.com/events",
            "name": "Example",
            "type": "blog",
            "reason": "Local events",
        }
    ]

    result = store_discovered_sources(session, sources, datetime.now(tz=timezone.utc))
    url = session.scalar(
        select(SourceUrl).where(SourceUrl.url == canonicalize_url(sources[0]["url"]))
    )
    assert url is not None
    assert url.notes is not None
    assert "domain_disabled" in url.notes
    assert result["active_urls"] == []


def test_store_sources_ignores_invalid_items() -> None:
    session = _make_session()
    sources = [
        "not a dict",
        {"name": "Missing url"},
        {"url": ""},
        {
            "url": "example.com/events",
            "name": "Example",
            "type": "museum",
            "reason": "Kids",
        },
    ]

    result = store_discovered_sources(session, sources, datetime.now(tz=timezone.utc))
    urls = session.scalars(select(SourceUrl)).all()

    assert len(urls) == 1
    assert result["total_returned"] == 4
    assert result["new_urls"] == 1
