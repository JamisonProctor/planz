from app.services.extract.llm_event_extractor import _build_completion_kwargs


def test_build_completion_kwargs_uses_lowest_reasoning_effort() -> None:
    kwargs = _build_completion_kwargs("body", "https://example.com")

    assert kwargs["model"] == "gpt-5.1"
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["response_format"] == {"type": "json_object"}
