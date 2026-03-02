from app.services.extract import llm_event_extractor


def test_build_completion_kwargs_uses_lowest_reasoning_effort() -> None:
    kwargs = llm_event_extractor._build_completion_kwargs("body", "https://example.com")

    assert kwargs["model"] == "gpt-5.1"
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["response_format"] == {"type": "json_object"}


def test_summarize_event_detail_returns_summary_and_cost(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class FakeCompletions:
        def create(self, **kwargs):
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {
                                        "content": (
                                            '{"summary": "Family music day with workshops.", '
                                            '"cost": "3 Euro"}'
                                        )
                                    },
                                )()
                            },
                        )()
                    ]
                },
            )()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.chat = FakeChat()

    monkeypatch.setattr(llm_event_extractor, "OpenAI", FakeOpenAI)

    summary = llm_event_extractor.summarize_event_detail(
        "Plain detail text",
        source_url="https://example.com/event",
    )

    assert summary == {
        "summary": "Family music day with workshops.",
        "cost": "3 Euro",
    }
