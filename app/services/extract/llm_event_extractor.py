import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-4o-mini"


def extract_events_from_text(text: str, source_url: str) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    prompt = (
        "Return STRICT JSON only. Extract real-world events from the provided text. "
        "Output a JSON object with a single key `events` containing objects with: "
        "title, start_time, end_time, location. Use ISO 8601 with Europe/Berlin timezone "
        "when possible. If end_time is unknown, omit it."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You return JSON only."},
            {
                "role": "user",
                "content": f"Source URL: {source_url}\n\nText:\n{text}",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON for extraction")
        return []

    events = data.get("events", [])
    if not isinstance(events, list):
        return []

    return events
