from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.migrations.external_key import ensure_external_keys


def _get_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def ensure_sqlite_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        columns = _get_columns(conn, "source_urls")
        if "last_extraction_count" not in columns:
            conn.execute(text("ALTER TABLE source_urls ADD COLUMN last_extraction_count INTEGER"))
        if "last_extraction_status" not in columns:
            conn.execute(text("ALTER TABLE source_urls ADD COLUMN last_extraction_status TEXT"))
        if "last_extraction_error" not in columns:
            conn.execute(text("ALTER TABLE source_urls ADD COLUMN last_extraction_error TEXT"))
        event_columns = _get_columns(conn, "events")
        if event_columns:
            if "external_key" not in event_columns:
                conn.execute(text("ALTER TABLE events ADD COLUMN external_key VARCHAR(255)"))
            if "is_calendar_candidate" not in event_columns:
                conn.execute(text("ALTER TABLE events ADD COLUMN is_calendar_candidate BOOLEAN NOT NULL DEFAULT 1"))
            if "google_event_id" not in event_columns:
                conn.execute(text("ALTER TABLE events ADD COLUMN google_event_id VARCHAR(255)"))
        if event_columns:
            if "category" not in event_columns:
                conn.execute(text("ALTER TABLE events ADD COLUMN category VARCHAR(50)"))
            if "is_paid" not in event_columns:
                conn.execute(text("ALTER TABLE events ADD COLUMN is_paid BOOLEAN NOT NULL DEFAULT 0"))
        series_columns = _get_columns(conn, "event_series")
        if series_columns:
            if "venue_address" not in series_columns:
                conn.execute(text("ALTER TABLE event_series ADD COLUMN venue_address TEXT"))
            if "is_paid" not in series_columns:
                conn.execute(text("ALTER TABLE event_series ADD COLUMN is_paid BOOLEAN NOT NULL DEFAULT 0"))
            if "category" not in series_columns:
                conn.execute(text("ALTER TABLE event_series ADD COLUMN category TEXT"))

    Base.metadata.create_all(engine)
    ensure_external_keys(engine)
