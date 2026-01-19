from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.db.models.source_url_discovery import SourceUrlDiscovery
from app.scripts.extract_muenchen_kinder import record_manual_discovery


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_record_manual_discovery_does_not_create_discovery() -> None:
    session = _make_session()
    domain = SourceDomain(domain="example.com")
    session.add(domain)
    session.flush()
    source_url = SourceUrl(url="https://example.com", domain_id=domain.id)
    session.add(source_url)
    session.flush()

    record_manual_discovery(session, source_url)
    session.commit()

    discovery = session.scalar(select(SourceUrlDiscovery))
    assert discovery is None
