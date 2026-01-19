from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.event_series import EventSeries
from app.services.extract.series_cache import enrich_with_series_cache


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_enrich_with_series_cache_fetches_once() -> None:
    session = _make_session()

    calls = {"count": 0}

    def fetch_detail(detail_url: str) -> str:
        calls["count"] += 1
        return "Detailed description"

    events = [
        {"title": "Show", "location": "Hall", "detail_url": "https://example.com/detail", "start_time": datetime.now(tz=timezone.utc)},
        {"title": "Show", "location": "Hall", "detail_url": "https://example.com/detail", "start_time": datetime.now(tz=timezone.utc)},
    ]

    enriched = enrich_with_series_cache(session, events, fetch_detail, now=datetime.now(tz=timezone.utc))

    descriptions = {e["description"] for e in enriched}
    assert descriptions == {"Detailed description"}
    assert calls["count"] == 1
    cached = session.scalar(select(EventSeries))
    assert cached is not None
    assert cached.detail_url == "https://example.com/detail"
