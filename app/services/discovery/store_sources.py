from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.urls import canonicalize_url, extract_domain
from app.db.models.source_domain import SourceDomain, get_or_create_domain
from app.db.models.source_url import SourceUrl


def store_discovered_sources(
    session: Session,
    sources: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    total_returned = len(sources)
    new_domains = 0
    new_urls = 0
    updated_urls = 0
    active_urls: list[tuple[str, str, str]] = []

    for item in sources:
        if not isinstance(item, dict):
            continue

        raw_url = item.get("url", "")
        name = str(item.get("name", "")).strip()
        source_type = str(item.get("type", "")).strip()
        reason = str(item.get("reason", "")).strip()

        canonical = canonicalize_url(raw_url)
        if not canonical:
            continue

        domain_str = extract_domain(canonical)
        if not domain_str:
            continue

        domain = session.scalar(
            select(SourceDomain).where(SourceDomain.domain == domain_str)
        )
        if domain is None:
            domain = get_or_create_domain(session, domain_str)
            new_domains += 1

        notes = f"name: {name} | type: {source_type} | reason: {reason}"
        if not domain.is_allowed:
            notes = f"{notes} | domain_disabled"

        existing_url = session.scalar(select(SourceUrl).where(SourceUrl.url == canonical))
        if existing_url is None:
            source_url = SourceUrl(
                url=canonical,
                domain_id=domain.id,
                first_seen_at=now,
                last_seen_at=now,
                discovery_method="llm_search",
                notes=notes,
            )
            session.add(source_url)
            new_urls += 1
        else:
            existing_url.domain_id = domain.id
            existing_url.last_seen_at = now
            existing_url.notes = notes
            updated_urls += 1

        if domain.is_allowed:
            active_urls.append((domain_str, canonical, name))

    session.commit()

    return {
        "total_returned": total_returned,
        "new_domains": new_domains,
        "new_urls": new_urls,
        "updated_urls": updated_urls,
        "active_urls": active_urls,
    }
