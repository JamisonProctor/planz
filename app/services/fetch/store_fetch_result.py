from __future__ import annotations

import hashlib
from datetime import datetime

from app.db.models.source_url import SourceUrl


def store_fetch_result(
    session,
    source_url: SourceUrl,
    text: str | None,
    error: str | None,
    now: datetime,
) -> None:
    if text is not None:
        source_url.fetch_status = "ok"
        source_url.last_fetched_at = now
        source_url.content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        source_url.content_excerpt = text[:2000]
        source_url.error_message = None
        session.add(source_url)
        return

    if error is not None:
        source_url.fetch_status = "error"
        source_url.last_fetched_at = now
        source_url.error_message = error
        session.add(source_url)
