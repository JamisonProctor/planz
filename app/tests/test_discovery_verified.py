from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.services.discovery.discover_sources import discover_and_store_sources


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_discovery_rejects_blocked_domains() -> None:
    session = _make_session()

    def llm_client():
        return [
            {
                "url": "https://meetup.com/muenchen/events",
                "name": "Meetup",
                "type": "other",
                "reason": "fallback",
            }
        ]

    def fetcher(url: str, timeout: float = 5.0):
        return "text" * 2000, None

    stats = discover_and_store_sources(
        session,
        llm_client=llm_client,
        http_fetcher=fetcher,
        now=datetime.now(tz=timezone.utc),
    )

    urls = session.scalars(select(SourceUrl)).all()
    assert urls == []
    assert stats["rejected"]["blocked_domain"] == 1


def test_discovery_rejects_fetch_failures() -> None:
    session = _make_session()

    def llm_client():
        return [
            {
                "url": "https://example.com/events",
                "name": "Example",
                "type": "museum",
                "reason": "kids",
            }
        ]

    def fetcher(url: str, timeout: float = 5.0):
        return None, "404"

    stats = discover_and_store_sources(
        session,
        llm_client=llm_client,
        http_fetcher=fetcher,
        now=datetime.now(tz=timezone.utc),
    )

    urls = session.scalars(select(SourceUrl)).all()
    assert urls == []
    assert stats["rejected"]["fetch_failed"] == 1


def test_discovery_rejects_too_short() -> None:
    session = _make_session()

    def llm_client():
        return [
            {
                "url": "https://example.com/short",
                "name": "Short",
                "type": "blog",
                "reason": "kids",
            },
            {
                "url": "https://example.com/long",
                "name": "Long",
                "type": "blog",
                "reason": "kids",
            },
        ]

    def fetcher(url: str, timeout: float = 5.0):
        if url.endswith("/short"):
            return "tiny", None
        return "still short" * 50, None

    stats = discover_and_store_sources(
        session,
        llm_client=llm_client,
        http_fetcher=fetcher,
        now=datetime.now(tz=timezone.utc),
    )

    urls = session.scalars(select(SourceUrl)).all()
    assert urls == []
    assert stats["rejected"]["too_short"] == 2


def test_discovery_accepts_good_url_and_persists() -> None:
    session = _make_session()

    def llm_client():
        return [
            {
                "url": "https://example.com/events",
                "name": "Example",
                "type": "museum",
                "reason": "kids",
            }
        ]

    def fetcher(url: str, timeout: float = 5.0):
        return ("Event on 12.03.2025 " * 200), None

    stats = discover_and_store_sources(
        session,
        llm_client=llm_client,
        http_fetcher=fetcher,
        now=datetime.now(tz=timezone.utc),
    )

    domain = session.scalar(select(SourceDomain))
    url = session.scalar(select(SourceUrl))
    assert domain is not None
    assert url is not None
    assert stats["accepted"] == 1
