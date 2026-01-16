import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from app.db.migrations.sqlite import ensure_sqlite_schema


def test_sqlite_migration_adds_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE source_urls (id TEXT PRIMARY KEY, url TEXT, domain_id TEXT)"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    ensure_sqlite_schema(engine)
    ensure_sqlite_schema(engine)

    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(source_urls)").fetchall()]
    conn.close()

    assert "last_extraction_count" in cols
    assert "last_extraction_status" in cols
    assert "last_extraction_error" in cols
