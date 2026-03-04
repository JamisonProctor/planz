"""Test that migrations add category + is_paid to events and category to event_series."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from app.db.migrations.sqlite import ensure_sqlite_schema


def _minimal_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE source_urls (id TEXT PRIMARY KEY, url TEXT, domain_id TEXT)")
    conn.execute(
        "CREATE TABLE events (id TEXT PRIMARY KEY, title TEXT, start_time TEXT, end_time TEXT, source_url TEXT)"
    )
    conn.execute(
        "CREATE TABLE event_series (id TEXT PRIMARY KEY, series_key TEXT UNIQUE)"
    )
    conn.commit()
    conn.close()


def _cols(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


def test_migration_adds_category_to_events(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _minimal_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_sqlite_schema(engine)
    assert "category" in _cols(db_path, "events")


def test_migration_adds_is_paid_to_events(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _minimal_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_sqlite_schema(engine)
    assert "is_paid" in _cols(db_path, "events")


def test_migration_adds_category_to_event_series(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _minimal_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_sqlite_schema(engine)
    assert "category" in _cols(db_path, "event_series")


def test_migration_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _minimal_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_sqlite_schema(engine)
    ensure_sqlite_schema(engine)  # should not raise
    assert "category" in _cols(db_path, "events")
    assert "is_paid" in _cols(db_path, "events")
    assert "category" in _cols(db_path, "event_series")
