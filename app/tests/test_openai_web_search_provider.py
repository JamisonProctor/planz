from app.services.search.openai_web_search import (
    OpenAIWebSearchProvider,
    _extract_sources,
    describe_action,
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


class _DummySource:
    def __init__(self):
        self.url = "https://example.com/obj"
        self.title = "ObjTitle"
        self.snippet = "ObjSnippet"


class _DummyLinkSource:
    def __init__(self):
        self.link = "https://example.com/link"
        self.name = "LinkTitle"
        self.text = "LinkSnippet"


class _FakeClientTypedSources:
    class responses:  # noqa: N801
        @staticmethod
        def create(**kwargs):
            return _FakeResponse(
                output=[
                    {
                        "type": "web_search_call",
                        "action": {"sources": [_DummySource(), _DummyLinkSource()]},
                    }
                ]
            )


def test_openai_web_search_provider_handles_typed_sources() -> None:
    provider = OpenAIWebSearchProvider(client=_FakeClientTypedSources())
    results = provider.search(
        query="kids events", language="en", location="Munich", max_results=5
    )

    assert len(results) == 2
    assert results[0].url == "https://example.com/obj"
    assert results[0].title == "ObjTitle"
    assert results[0].snippet == "ObjSnippet"
    assert results[1].url == "https://example.com/link"
    assert results[1].title == "LinkTitle"
    assert results[1].snippet == "LinkSnippet"


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


def test_describe_action_with_sources_and_dump() -> None:
    action = _DummyActionModelDump([{"url": "https://example.com/c"}])
    info = describe_action(action)
    assert info["has_sources"] is False
    assert info["sources_len"] == 0
    assert "sources" in info["dump_keys"]


def test_describe_action_with_sources_attr() -> None:
    action = _DummyAction([{"url": "https://example.com/b"}])
    info = describe_action(action)
    assert info["has_sources"] is True
    assert info["sources_len"] == 1


def test_extract_sources_prefers_attribute_over_model_dump() -> None:
    class _ActionWithBoth:
        def __init__(self):
            self.sources = [{"url": "https://example.com/attr"}]

        def model_dump(self):
            return {"sources": [{"url": "https://example.com/dump"}]}

    action = _ActionWithBoth()
    assert _extract_sources(action) == [{"url": "https://example.com/attr"}]


def test_extract_sources_uses_attribute_first() -> None:
    action = _DummyAction([{"url": "https://example.com/attr"}])
    assert _extract_sources(action) == [{"url": "https://example.com/attr"}]


def test_extract_sources_falls_back_to_model_dump() -> None:
    class _ActionNoAttr:
        def model_dump(self):
            return {"sources": [{"url": "https://example.com/dump"}]}

    action = _ActionNoAttr()
    assert _extract_sources(action) == [{"url": "https://example.com/dump"}]
