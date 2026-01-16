from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


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
