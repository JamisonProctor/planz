from datetime import datetime, timezone
import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.services.fetch.store_fetch_result import store_fetch_result


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _create_source_url(session) -> SourceUrl:
    domain = SourceDomain(domain="example.com")
    session.add(domain)
    session.flush()
    source_url = SourceUrl(url="https://example.com/events", domain_id=domain.id)
    session.add(source_url)
    session.commit()
    session.refresh(source_url)
    return source_url


def test_store_fetch_result_success_sets_fields() -> None:
    session = _make_session()
    source_url = _create_source_url(session)
    now = datetime.now(tz=timezone.utc)
    text = "hello" * 500

    store_fetch_result(session, source_url, text=text, error=None, now=now)

    assert source_url.fetch_status == "ok"
    assert source_url.last_fetched_at == now
    assert source_url.content_hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert source_url.content_excerpt == text[:2000]
    assert source_url.error_message is None


def test_store_fetch_result_error_does_not_overwrite_content() -> None:
    session = _make_session()
    source_url = _create_source_url(session)
    source_url.content_hash = "existing"
    source_url.content_excerpt = "previous excerpt"
    session.commit()

    now = datetime.now(tz=timezone.utc)
    store_fetch_result(session, source_url, text=None, error="boom", now=now)

    assert source_url.fetch_status == "error"
    assert source_url.last_fetched_at == now
    assert source_url.error_message == "boom"
    assert source_url.content_hash == "existing"
    assert source_url.content_excerpt == "previous excerpt"
