"""Test LLM categorization: EventPageSummary has category; invalid output falls back to 'other'."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.services.llm.summarizer import EventPageSummary, summarize_event_page


def _mock_openai_response(data: dict) -> MagicMock:
    message = MagicMock()
    message.content = json.dumps(data)
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_event_page_summary_has_category_field() -> None:
    s = EventPageSummary(summary="test", is_paid=False, address=None, category="theater")
    assert s.category == "theater"


def test_summarize_returns_valid_category() -> None:
    fake_data = {
        "summary": "A puppet theater show for children.",
        "is_paid": False,
        "address": None,
        "category": "theater",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(fake_data)

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Puppet theater show page text.")

    assert result is not None
    assert result.category == "theater"


def test_summarize_returns_museum_category() -> None:
    fake_data = {
        "summary": "A museum visit for families.",
        "is_paid": True,
        "address": "Museumstrasse 1, 80538 München",
        "category": "museum",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(fake_data)

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Museum page text.")

    assert result is not None
    assert result.category == "museum"


def test_invalid_category_falls_back_to_other() -> None:
    fake_data = {
        "summary": "An event for kids.",
        "is_paid": False,
        "address": None,
        "category": "invalid_category",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(fake_data)

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Some event text.")

    assert result is not None
    assert result.category == "other"


def test_missing_category_falls_back_to_other() -> None:
    fake_data = {
        "summary": "An event for kids.",
        "is_paid": False,
        "address": None,
        # no "category" key
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(fake_data)

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Some event text.")

    assert result is not None
    assert result.category == "other"


def test_all_valid_categories_accepted() -> None:
    from app.domain.constants import EVENT_CATEGORIES

    for cat in EVENT_CATEGORIES:
        fake_data = {
            "summary": f"A {cat} event.",
            "is_paid": False,
            "address": None,
            "category": cat,
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(fake_data)

        with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
            result = summarize_event_page("Event text.")

        assert result is not None
        assert result.category == cat


def test_system_prompt_includes_category_instructions() -> None:
    from app.services.llm.summarizer import _SYSTEM_PROMPT

    assert "category" in _SYSTEM_PROMPT
    assert "theater" in _SYSTEM_PROMPT
    assert "museum" in _SYSTEM_PROMPT
    assert "workshop" in _SYSTEM_PROMPT
