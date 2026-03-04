"""Backfill EventSeries.category via minimal LLM prompt for rows where category IS NULL."""
from __future__ import annotations

import logging
import os

from openai import OpenAI
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models.event import Event
from app.db.models.event_series import EventSeries
from app.domain.constants import EVENT_CATEGORIES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_MODEL = "gpt-4.1-nano"
_VALID = set(EVENT_CATEGORIES)


def _categorize(client: OpenAI, title: str, description: str) -> str:
    prompt = (
        f"Event title: {title}\nDescription: {description[:500]}\n\n"
        f'Return exactly one word — the category of this kids event: '
        f'{", ".join(EVENT_CATEGORIES)}'
    )
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip().lower()
        return raw if raw in _VALID else "other"
    except Exception:
        logger.exception("Categorization failed for title=%r", title)
        return "other"


def backfill_categories() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    with SessionLocal() as session:
        series_list = session.scalars(
            select(EventSeries).where(
                EventSeries.category == None,  # noqa: E711
                EventSeries.description != None,  # noqa: E711
            )
        ).all()
        logger.info("Found %d series needing categorization", len(series_list))

        for series in series_list:
            category = _categorize(client, series.title or "", series.description or "")
            series.category = category

            # Propagate to linked Event rows
            events = session.scalars(
                select(Event).where(Event.source_url == series.detail_url)
            ).all()
            for event in events:
                event.category = category

        session.commit()
        logger.info("Backfill complete")


if __name__ == "__main__":
    backfill_categories()
