from __future__ import annotations

import logging
import os
from typing import Any

from openai import OpenAI

from app.core.urls import extract_domain
from app.services.search.base import SearchProvider
from app.services.search.types import SearchResultItem

logger = logging.getLogger(__name__)


class OpenAIWebSearchProvider(SearchProvider):
    def __init__(self, client: OpenAI | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if client is None:
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY is not set")
            client = OpenAI(api_key=api_key)
        self._client = client

    def search(
        self,
        query: str,
        language: str,
        location: str,
        max_results: int,
    ) -> list[SearchResultItem]:
        input_text = f"{query}\nLanguage: {language}\nLocation: {location}"
        response = self._client.responses.create(
            model="gpt-4o-mini",
            input=input_text,
            tools=[{"type": "web_search"}],
            tool_choice={"type": "web_search"},
            include=["web_search_call.action.sources"],
        )

        raw_items = _extract_search_results(response)
        if os.getenv("PLANZ_SEARCH_DEBUG", "").strip().lower() in {"true", "1", "yes"}:
            first_call = _first_web_search_call(response)
            if first_call is not None:
                logger.info("web_search_call action: %s", describe_action(first_call))
            logger.info(
                "web_search_call items: %s, extracted_sources: %s",
                _count_web_search_calls(response),
                len(raw_items),
            )
            if raw_items:
                logger.info(
                    "source_item: %s",
                    _describe_source_item(raw_items[0]),
                )

        results: list[SearchResultItem] = []
        for idx, item in enumerate(raw_items[:max_results], start=1):
            url = extract_source_url(item)
            if not url:
                continue
            results.append(
                SearchResultItem(
                    url=url,
                    title=extract_source_title(item),
                    snippet=extract_source_snippet(item),
                    rank=idx,
                    domain=extract_domain(url),
                )
            )

        if os.getenv("PLANZ_SEARCH_DEBUG", "").strip().lower() in {"true", "1", "yes"}:
            logger.info("normalized_results: %s", len(results))

        return results


def _extract_search_results(response: Any) -> list[Any]:
    results: list[Any] = []
    for item in _iter_output_items(response):
        if _is_web_search_call(item):
            results.extend(_get_sources(item))
    return results


def _iter_output_items(response: Any) -> list[Any]:
    items: list[Any] = []
    output = getattr(response, "output", None) or []
    items.extend(output)
    included = getattr(response, "included", None) or []
    items.extend(included)
    return items


def _is_web_search_call(item: Any) -> bool:
    if isinstance(item, dict):
        return item.get("type") == "web_search_call"
    return getattr(item, "type", None) == "web_search_call"


def _extract_sources(action: Any) -> list[Any]:
    if hasattr(action, "sources"):
        sources = getattr(action, "sources") or []
    elif isinstance(action, dict):
        sources = action.get("sources", [])
    elif hasattr(action, "model_dump"):
        sources = (action.model_dump() or {}).get("sources", [])
    else:
        sources = []

    if not isinstance(sources, list):
        return []
    return sources


def _get_sources(item: Any) -> list[dict[str, Any]]:
    if isinstance(item, dict):
        return _extract_sources(item.get("action") or {})
    action = getattr(item, "action", None)
    return _extract_sources(action)


def _count_web_search_calls(response: Any) -> int:
    return sum(1 for item in _iter_output_items(response) if _is_web_search_call(item))


def _first_web_search_call(response: Any) -> Any:
    for item in _iter_output_items(response):
        if _is_web_search_call(item):
            if isinstance(item, dict):
                return item.get("action")
            return getattr(item, "action", None)
    return None


def describe_action(action: Any) -> dict[str, Any]:
    dump_keys: list[str] = []
    if action is None:
        return {"action_type": "None", "has_sources": False, "sources_len": 0, "dump_keys": []}

    if hasattr(action, "model_dump"):
        try:
            dump = action.model_dump()
            if isinstance(dump, dict):
                dump_keys = list(dump.keys())
        except Exception:
            dump_keys = []

    sources = getattr(action, "sources", None)
    has_sources = sources is not None
    sources_len = len(sources) if isinstance(sources, list) else 0

    return {
        "action_type": type(action).__name__,
        "has_sources": has_sources,
        "sources_len": sources_len,
        "dump_keys": dump_keys,
    }


def extract_source_url(source: Any) -> str | None:
    if isinstance(source, dict):
        return source.get("url") or source.get("link") or source.get("href")
    if hasattr(source, "url"):
        return getattr(source, "url")
    if hasattr(source, "link"):
        return getattr(source, "link")
    if hasattr(source, "href"):
        return getattr(source, "href")
    if hasattr(source, "model_dump"):
        data = source.model_dump()
        if isinstance(data, dict):
            return data.get("url") or data.get("link") or data.get("href")
    return None


def extract_source_title(source: Any) -> str | None:
    if isinstance(source, dict):
        return source.get("title") or source.get("name")
    if hasattr(source, "title"):
        return getattr(source, "title")
    if hasattr(source, "name"):
        return getattr(source, "name")
    if hasattr(source, "model_dump"):
        data = source.model_dump()
        if isinstance(data, dict):
            return data.get("title") or data.get("name")
    return None


def extract_source_snippet(source: Any) -> str | None:
    if isinstance(source, dict):
        return source.get("snippet") or source.get("text") or source.get("description")
    if hasattr(source, "snippet"):
        return getattr(source, "snippet")
    if hasattr(source, "text"):
        return getattr(source, "text")
    if hasattr(source, "description"):
        return getattr(source, "description")
    if hasattr(source, "model_dump"):
        data = source.model_dump()
        if isinstance(data, dict):
            return (
                data.get("snippet")
                or data.get("text")
                or data.get("description")
            )
    return None


def _describe_source_item(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return {"source_type": "dict", "keys": list(source.keys())}
    attr_names = []
    for name in ("url", "link", "href", "title", "name", "snippet", "text", "description"):
        if hasattr(source, name):
            attr_names.append(name)
    return {"source_type": type(source).__name__, "attrs": attr_names}
