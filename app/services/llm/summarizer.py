from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)

_MODEL = "gpt-4.1-nano"
_MAX_INPUT_CHARS = 4000
_SYSTEM_PROMPT = (
    "You are a helpful assistant for parents in Munich. "
    "Return a JSON object with exactly three fields:\n"
    '- "summary": 2-3 sentences in English describing the event for parents, including target age range and key family appeal\n'
    '- "is_paid": true if the event requires an admission fee or ticket purchase; '
    'German indicators include: "Karten", "Eintrittskarten", "Eintritt", "Tickets", '
    '"Abendkasse", "kostenpflichtig", "Ticketpreis", "VVK", "Vorverkauf"; '
    'set false only if the page explicitly states it is free ("kostenlos", "freier Eintritt", "Eintritt frei")\n'
    '- "address": the full street address and city (e.g. "Museumstrasse 1, 80538 München"), or null if not found\n'
    "Return only valid JSON. Do not include any other text."
)


@dataclass
class EventPageSummary:
    summary: str
    is_paid: bool
    address: str | None


def summarize_event_page(text: str) -> EventPageSummary | None:
    """Return a structured summary of an event page, or None on failure."""
    if not text:
        return None

    truncated = text[:_MAX_INPUT_CHARS]
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": truncated},
            ],
            max_tokens=300,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            logger.warning("LLM response missing valid summary field")
            return None
        is_paid = bool(data.get("is_paid", False))
        address = data.get("address")
        if not isinstance(address, str):
            address = None
        return EventPageSummary(summary=summary.strip(), is_paid=is_paid, address=address)
    except Exception:
        logger.exception("LLM summarization failed")
        return None
