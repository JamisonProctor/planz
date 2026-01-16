from app.services.search.openai_web_search import OpenAIWebSearchProvider


class _FakeResponse:
    def __init__(self, output):
        self.output = output


class _FakeClient:
    class responses:  # noqa: N801
        @staticmethod
        def create(**kwargs):
            return _FakeResponse(
                [
                    {
                        "type": "web_search",
                        "results": [
                            {
                                "url": "https://example.com/page",
                                "title": "Example",
                                "snippet": "Snippet",
                            }
                        ],
                    }
                ]
            )


def test_openai_web_search_provider_returns_normalized_results() -> None:
    provider = OpenAIWebSearchProvider(client=_FakeClient())
    results = provider.search(
        query="kids events", language="en", location="Munich", max_results=5
    )

    assert len(results) == 1
    assert results[0].url == "https://example.com/page"
    assert results[0].rank == 1
    assert results[0].domain == "example.com"
