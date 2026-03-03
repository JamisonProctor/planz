from __future__ import annotations

import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

_MODEL = "gpt-4.1-nano"
_MAX_INPUT_CHARS = 4000
_SYSTEM_PROMPT = (
    "You are a helpful assistant for parents in Munich. "
    "Summarize the following event page in 2-3 sentences in English. "
    "Include the target age range and the key appeal for families."
)


def summarize_event_page(text: str) -> str | None:
    """Return a 2-3 sentence English summary of an event page, or None on failure."""
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
            max_tokens=200,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception:
        logger.exception("LLM summarization failed")
        return None
