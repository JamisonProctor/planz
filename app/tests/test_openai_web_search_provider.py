from app.services.search.openai_web_search import OpenAIWebSearchProvider


class _FakeResponse:
    def __init__(self, output, included=None):
        self.output = output
        self.included = included or []


class _FakeClient:
    class responses:  # noqa: N801
        @staticmethod
        def create(**kwargs):
            return _FakeResponse(
                output=[
                    {
                        "type": "web_search_call",
                        "action": {"sources": [{"url": "https://example.com/a", "title": "A", "snippet": "S"}]},
                    }
                ],
                included=[
                    {
                        "type": "web_search_call",
                        "action": {"sources": [{"url": "https://example.com/b", "title": "B", "snippet": "T"}]},
                    }
                ],
            )


def test_openai_web_search_provider_returns_normalized_results() -> None:
    provider = OpenAIWebSearchProvider(client=_FakeClient())
    results = provider.search(
        query="kids events", language="en", location="Munich", max_results=5
    )

    urls = {item.url for item in results}
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls
    assert results[0].rank == 1
