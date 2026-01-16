from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models.acquisition_issue import AcquisitionIssue


def upsert_acquisition_issue(
    session,
    *,
    url: str,
    domain: str,
    reason: str,
    now: datetime,
    http_status: int | None = None,
    content_length: int | None = None,
    discovered_search_result_id: str | None = None,
    notes: str | None = None,
) -> AcquisitionIssue:
    existing = session.scalar(select(AcquisitionIssue).where(AcquisitionIssue.url == url))
    if existing:
        existing.last_seen_at = now
        existing.reason = reason
        existing.http_status = http_status
        existing.content_length = content_length
        existing.discovered_search_result_id = discovered_search_result_id
        existing.notes = notes
        return existing

    issue = AcquisitionIssue(
        url=url,
        domain=domain,
        reason=reason,
        first_seen_at=now,
        last_seen_at=now,
        http_status=http_status,
        content_length=content_length,
        discovered_search_result_id=discovered_search_result_id,
        notes=notes,
    )
    session.add(issue)
    return issue
