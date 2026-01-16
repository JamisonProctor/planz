from app.services.search.openai_web_search import (
    OpenAIWebSearchProvider,
    _extract_sources,
)


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


class _DummyAction:
    def __init__(self, sources):
        self.sources = sources


class _DummyActionModelDump:
    def __init__(self, sources):
        self._sources = sources

    def model_dump(self):
        return {"sources": self._sources}


def test_extract_sources_from_dict_action() -> None:
    action = {"sources": [{"url": "https://example.com/a"}]}
    assert _extract_sources(action) == [{"url": "https://example.com/a"}]


def test_extract_sources_from_object_action() -> None:
    action = _DummyAction([{"url": "https://example.com/b"}])
    assert _extract_sources(action) == [{"url": "https://example.com/b"}]


def test_extract_sources_from_model_dump_action() -> None:
    action = _DummyActionModelDump([{"url": "https://example.com/c"}])
    assert _extract_sources(action) == [{"url": "https://example.com/c"}]
