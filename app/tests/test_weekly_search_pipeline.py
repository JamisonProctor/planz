from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.scripts.run_weekly import run_weekly_pipeline


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_weekly_pipeline_runs_search_and_stages(monkeypatch):
    session = _make_session()
    now = datetime.now(tz=timezone.utc)

    called = {"search": 0, "fetch": 0, "extract": 0, "sync": 0}

    def search_runner(*args, **kwargs):
        called["search"] += 1
        return {"accepted": 1}

    def fetch_runner():
        called["fetch"] += 1
        return {"fetched_ok": 0, "fetched_error": 0}

    def extract_runner():
        called["extract"] += 1
        return {
            "sources_processed": 0,
            "events_created_total": 0,
            "sources_skipped_no_content": 0,
            "sources_skipped_unchanged_hash": 0,
            "sources_skipped_disabled_domain": 0,
            "sources_empty_extraction": 0,
            "sources_error_extraction": 0,
            "sources_past_only": 0,
        }

    def sync_runner(*args, **kwargs):
        called["sync"] += 1
        return {"synced_count": 0, "skipped_already_synced": 0, "skipped_too_old": 0}

    monkeypatch.setenv("PLANZ_ENABLE_SEARCH", "true")

    run_weekly_pipeline(
        session=session,
        now=now,
        search_runner=search_runner,
        search_provider_factory=None,
        fetch_runner=fetch_runner,
        extract_runner=extract_runner,
        sync_runner=sync_runner,
        calendar_client_factory=None,
    )

    assert called == {"search": 1, "fetch": 1, "extract": 1, "sync": 1}
