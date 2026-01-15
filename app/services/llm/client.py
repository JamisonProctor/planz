import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-4o-mini"


def generate_kids_events_munich() -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    prompt = (
        "Return STRICT JSON only. Output a JSON object with a single key `events` "
        "containing 3 to 6 realistic kids/family events in Munich within the next 14 days. "
        "All events must be free or low-cost. Each event object must include: "
        "title, start_time, end_time, location, description, source_url. "
        "Use ISO 8601 with timezone Europe/Berlin for start_time and end_time."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You return JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON")
        return []

    events = data.get("events", [])
    if not isinstance(events, list):
        return []

    return events
