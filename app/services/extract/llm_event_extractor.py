import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-5.1"
REASONING_EFFORT = "none"


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
        **_build_completion_kwargs(text, source_url, prompt)
    )

    data = _parse_json_object(
        response.choices[0].message.content or "{}",
        error_message="LLM returned invalid JSON for extraction",
    )
    if not data:
        return []

    events = data.get("events", [])
    if not isinstance(events, list):
        return []

    return events


def summarize_event_detail(text: str, source_url: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        **_build_summary_completion_kwargs(text, source_url)
    )
    data = _parse_json_object(
        response.choices[0].message.content or "{}",
        error_message="LLM returned invalid JSON for detail summary",
    )
    if not data:
        return {}

    summary: dict[str, Any] = {}
    summary_text = data.get("summary")
    if isinstance(summary_text, str) and summary_text.strip():
        summary["summary"] = summary_text.strip()

    cost = data.get("cost")
    if isinstance(cost, str) and cost.strip():
        summary["cost"] = cost.strip()

    return summary


def _build_completion_kwargs(
    text: str,
    source_url: str,
    prompt: str = (
        "Return STRICT JSON only. Extract real-world events from the provided text. "
        "Output a JSON object with a single key `events` containing objects with: "
        "title, start_time, end_time, location. Use ISO 8601 with Europe/Berlin timezone "
        "when possible. If end_time is unknown, omit it."
    ),
) -> dict[str, Any]:
    return {
        "model": MODEL_NAME,
        "reasoning_effort": REASONING_EFFORT,
        "messages": [
            {"role": "system", "content": "You return JSON only."},
            {
                "role": "user",
                "content": f"Source URL: {source_url}\n\nText:\n{text}",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }


def _build_summary_completion_kwargs(text: str, source_url: str) -> dict[str, Any]:
    prompt = (
        "Return STRICT JSON only. Summarize the event details in 1-3 sentences using only facts "
        "present in the text. Output a JSON object with `summary` and optional `cost`. "
        "If price or ticket cost is explicitly stated, include it in `cost`. Do not invent dates, "
        "times, locations, or prices."
    )
    return _build_completion_kwargs(text, source_url, prompt=prompt)


def _parse_json_object(content: str, error_message: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.error(error_message)
        return {}
    if not isinstance(data, dict):
        return {}
    return data
