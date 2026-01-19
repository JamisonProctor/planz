from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.scripts.extract_muenchen_kinder import prepare_source_url


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
