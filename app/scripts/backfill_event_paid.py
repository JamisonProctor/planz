"""Backfill Event.is_paid from EventSeries.is_paid for existing rows via series_key join."""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models.event import Event
from app.db.models.event_series import EventSeries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_event_paid() -> None:
    with SessionLocal() as session:
        events = session.scalars(select(Event)).all()
        updated = 0
        for event in events:
            if event.external_key is None:
                continue
            # Find matching series by external_key prefix (detail_url based)
            # Events created from series have external_key = sha256(detail_url|start_time)
            # We join via series that share the same detail_url stored in source_url or description
            # Best approach: match via detail_url by comparing series keys
            series_list = session.scalars(
                select(EventSeries).where(EventSeries.detail_url == event.source_url)
            ).all()
            if not series_list:
                continue
            series = series_list[0]
            if event.is_paid != series.is_paid:
                event.is_paid = series.is_paid
                updated += 1

        session.commit()
        logger.info("Backfilled is_paid for %d events", updated)


if __name__ == "__main__":
    backfill_event_paid()
