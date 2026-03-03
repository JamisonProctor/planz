from unittest.mock import MagicMock, patch

from app.services.llm.summarizer import summarize_event_page


def _mock_openai_response(text: str) -> MagicMock:
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_summarize_event_page_returns_summary() -> None:
    fake_response = _mock_openai_response("A fun family event for kids aged 5-10.")

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch("app.services.llm.summarizer.OpenAI", return_value=mock_client):
        result = summarize_event_page("Some event page text about a kids festival.")

    assert result == "A fun family event for kids aged 5-10."


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
