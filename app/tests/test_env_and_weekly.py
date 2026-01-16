from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.env import load_env
from app.db.base import Base
from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.scripts.run_weekly import run_weekly_pipeline


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_load_env_does_not_fail_when_missing() -> None:
    load_env()


def test_run_weekly_reports_no_sources(capsys) -> None:
    session = _make_session()

    def fetch_runner():
        return {"fetched_ok": 0, "fetched_error": 0}

    def extract_runner():
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
        return 0

    run_weekly_pipeline(
        session=session,
        now=datetime.now(tz=timezone.utc),
        fetch_runner=fetch_runner,
        extract_runner=extract_runner,
        sync_runner=sync_runner,
        calendar_client_factory=None,
    )

    captured = capsys.readouterr().out
    assert "No allowed sources to fetch" in captured


def test_run_weekly_reports_missing_openai_key_when_needed(monkeypatch, capsys) -> None:
    session = _make_session()
    domain = SourceDomain(domain="example.com", is_allowed=True)
    session.add(domain)
    session.flush()
    session.add(
        SourceUrl(
            url="https://example.com/events",
            domain_id=domain.id,
            fetch_status="ok",
            content_excerpt="content",
            content_hash="hash-a",
            last_extracted_hash="hash-b",
        )
    )
    session.commit()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fetch_runner():
        return {"fetched_ok": 0, "fetched_error": 0}

    def extract_runner():
        raise AssertionError("extract should be skipped when OPENAI_API_KEY missing")

    def sync_runner(*args, **kwargs):
        return 0

    run_weekly_pipeline(
        session=session,
        now=datetime.now(tz=timezone.utc),
        fetch_runner=fetch_runner,
        extract_runner=extract_runner,
        sync_runner=sync_runner,
        calendar_client_factory=None,
    )

    captured = capsys.readouterr().out
    assert "OPENAI_API_KEY missing: extraction skipped" in captured


def test_extraction_skip_reason_unchanged_hash_reported(capsys) -> None:
    session = _make_session()
    domain = SourceDomain(domain="example.com", is_allowed=True)
    session.add(domain)
    session.flush()
    session.add(
        SourceUrl(
            url="https://example.com/events",
            domain_id=domain.id,
            fetch_status="ok",
            content_excerpt="content",
            content_hash="hash-a",
            last_extracted_hash="hash-a",
        )
    )
    session.commit()

    def fetch_runner():
        return {"fetched_ok": 0, "fetched_error": 0}

    def extract_runner():
        return {
            "sources_processed": 0,
            "events_created_total": 0,
            "sources_skipped_no_content": 0,
            "sources_skipped_unchanged_hash": 1,
            "sources_skipped_disabled_domain": 0,
            "sources_empty_extraction": 0,
            "sources_error_extraction": 0,
            "sources_past_only": 0,
        }

    def sync_runner(*args, **kwargs):
        return 0

    run_weekly_pipeline(
        session=session,
        now=datetime.now(tz=timezone.utc),
        fetch_runner=fetch_runner,
        extract_runner=extract_runner,
        sync_runner=sync_runner,
        calendar_client_factory=None,
    )

    captured = capsys.readouterr().out
    assert "Extraction skipped: all content hashes unchanged" in captured
