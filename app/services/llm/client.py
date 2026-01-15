import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-4o-mini"


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def _parse_json(content: str) -> dict[str, Any] | None:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def generate_kids_events_munich() -> list[dict[str, Any]]:
    client = _get_client()
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
    data = _parse_json(content)
    if data is None:
        logger.error("LLM returned invalid JSON")
        return []

    events = data.get("events", [])
    if not isinstance(events, list):
        return []

    return events


def discover_munich_kids_event_sources() -> list[dict[str, Any]]:
    client = _get_client()
    prompt = (
        "Return STRICT JSON only. Output a JSON object with a single key `sources` "
        "containing 15 to 25 candidate source URLs for kids/family events in Munich. "
        "Focus on primary publishers (venues, museums, libraries, city portals), "
        "prefer program or calendar pages listing multiple events, and avoid aggregators. "
        "You may include 1-2 fallback aggregators like Meetup or Eventbrite. "
        "Each source must include: url, name, type, reason. "
        "Type must be one of: venue_calendar, city_portal, museum, library, blog, other. "
        "JSON only, no markdown."
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
    data = _parse_json(content)
    if data is None:
        repair_prompt = (
            "Return valid JSON only. Fix this into a JSON object with a `sources` list:\n"
            f"{content}"
        )
        repair_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You return JSON only."},
                {"role": "user", "content": repair_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        repaired = repair_response.choices[0].message.content or "{}"
        data = _parse_json(repaired)

    if data is None:
        logger.error("LLM returned invalid JSON for sources")
        return []

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        return []

    return sources
