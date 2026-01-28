from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _build_external_key(source_url: str | None, title: str | None, start_time: datetime | None) -> str:
    base = source_url or title or str(uuid.uuid4())
    ts = start_time.isoformat() if isinstance(start_time, datetime) else str(uuid.uuid4())
    raw = f"{base}|{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()


def ensure_external_keys(engine: Engine) -> None:
    with engine.begin() as conn:
        columns = _get_columns(conn, "events")
        if "external_key" not in columns:
            conn.execute(text("ALTER TABLE events ADD COLUMN external_key VARCHAR(255)"))

        rows = conn.execute(
            text("SELECT id, external_key, source_url, title, start_time FROM events")
        ).fetchall()
        seen: set[str] = set()
        for row in rows:
            key = row.external_key
            if not key:
                key = _build_external_key(row.source_url, row.title, row.start_time)
            base_key = key
            suffix = 1
            while key in seen:
                key = _hash_with_suffix(base_key, suffix)
                suffix += 1
            seen.add(key)
            conn.execute(
                text("UPDATE events SET external_key=:key WHERE id=:id"),
                {"key": key, "id": row.id},
            )

        indexes = _get_indexes(conn, "events")
        if not any("external_key" in idx for idx in indexes):
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ux_events_external_key ON events(external_key)")
            )


def _get_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _get_indexes(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA index_list({table})")).fetchall()
    return {row[1] for row in rows}


def _hash_with_suffix(base: str, suffix: int) -> str:
    raw = f"{base}:{suffix}"
    return hashlib.sha256(raw.encode()).hexdigest()
