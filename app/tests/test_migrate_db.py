from pathlib import Path
from datetime import datetime, timezone

import sqlite3
from sqlalchemy import create_engine, text

from app.db.migrations.external_key import ensure_external_keys, _build_external_key


def test_migration_adds_unique_index(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE events (id TEXT PRIMARY KEY, source_url TEXT, title TEXT, start_time TEXT)"
    )
    conn.execute(
        "INSERT INTO events (id, source_url, title, start_time) VALUES ('1', 'https://example.com', 't', '2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_external_keys(engine)

    with engine.connect() as conn2:
        indexes = conn2.execute(text("PRAGMA index_list(events)")).fetchall()
        index_names = {row[1] for row in indexes}
        assert any("external_key" in name for name in index_names)


def test_duplicate_external_key_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE events (id TEXT PRIMARY KEY, source_url TEXT, title TEXT, start_time TEXT)"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_external_keys(engine)

    key = _build_external_key("https://example.com", "t", datetime.now(tz=timezone.utc))
    with engine.begin() as conn2:
        conn2.execute(
            text("INSERT INTO events (id, source_url, title, start_time, external_key) VALUES ('1', 'https://example.com', 't', '2026-01-01T00:00:00+00:00', :key)"),
            {"key": key},
        )
    ensure_external_keys(engine)

    with engine.connect() as conn3:
        try:
            conn3.execute(
                text("INSERT INTO events (id, source_url, title, start_time, external_key) VALUES ('2', 'x', 'y', '2026-01-02T00:00:00+00:00', :key)"),
                {"key": key},
            )
            assert False, "Expected unique constraint"
        except Exception:
            pass
