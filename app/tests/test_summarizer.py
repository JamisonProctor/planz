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


def test_summarize_event_page_returns_summary() -> None:
    fake_data = {
        "summary": "A fun family event for kids aged 5-10.",
        "is_paid": False,
        "address": None,
    }
    fake_response = _mock_openai_response(fake_data)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Some event page text about a kids festival.")

    assert isinstance(result, EventPageSummary)
    assert result.summary == "A fun family event for kids aged 5-10."
    assert result.is_paid is False
    assert result.address is None


def test_summarize_event_page_is_paid_true() -> None:
    fake_data = {
        "summary": "A ticketed theater show for children.",
        "is_paid": True,
        "address": None,
    }
    fake_response = _mock_openai_response(fake_data)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Theater show page text.")

    assert isinstance(result, EventPageSummary)
    assert result.is_paid is True
    assert result.summary == "A ticketed theater show for children."


def test_summarize_event_page_includes_address() -> None:
    fake_data = {
        "summary": "A museum exhibit for families.",
        "is_paid": False,
        "address": "Museumstrasse 1, 80538 München",
    }
    fake_response = _mock_openai_response(fake_data)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Museum exhibit page text.")

    assert isinstance(result, EventPageSummary)
    assert result.address == "Museumstrasse 1, 80538 München"
    assert result.summary == "A museum exhibit for families."


def test_summarize_event_page_system_prompt_includes_german_paid_indicators() -> None:
    """The system prompt must contain German ticket keywords so the LLM can detect paid German-language pages."""
    from app.services.llm.summarizer import _SYSTEM_PROMPT

    german_paid_indicators = ["Karten", "Abendkasse", "Eintritt", "Vorverkauf"]
    for indicator in german_paid_indicators:
        assert indicator in _SYSTEM_PROMPT, f"System prompt missing German paid indicator: {indicator!r}"


def test_summarize_event_page_is_paid_true_for_german_abendkasse_text() -> None:
    """LLM response for page mentioning Abendkasse must yield is_paid=True."""
    fake_data = {
        "summary": "A world-class circus show suitable for children aged 6 and up.",
        "is_paid": True,
        "address": "Olympiapark, 80809 München",
    }
    fake_response = _mock_openai_response(fake_data)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    german_page_text = (
        "Cirque du Soleil: Alegria. "
        "Karten sind online oder an der Abendkasse erhältlich. "
        "Vorverkauf ab 29 €. Olympiapark München."
    )

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page(german_page_text)

    assert isinstance(result, EventPageSummary)
    assert result.is_paid is True


def test_summarize_event_page_returns_none_on_api_error() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API error")

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Some event page text.")

    assert result is None


def test_summarize_event_page_returns_none_for_empty_text() -> None:
    with patch("app.services.llm.summarizer.OpenAI") as mock_openai_cls:
        result = summarize_event_page("")

    mock_openai_cls.assert_not_called()
    assert result is None
