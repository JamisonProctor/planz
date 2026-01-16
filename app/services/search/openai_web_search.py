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
            logger.info(
                "web_search_call items: %s, sources: %s",
                _count_web_search_calls(response),
                len(raw_items),
            )
            for item in raw_items[:3]:
                logger.info("sample url: %s", item.get("url"))

        results: list[SearchResultItem] = []
        for idx, item in enumerate(raw_items[:max_results], start=1):
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResultItem(
                    url=url,
                    title=item.get("title"),
                    snippet=item.get("snippet"),
                    rank=idx,
                    domain=extract_domain(url),
                )
            )

        return results


def _extract_search_results(response: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
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


def _get_sources(item: Any) -> list[dict[str, Any]]:
    if isinstance(item, dict):
        return (item.get("action") or {}).get("sources", [])
    action = getattr(item, "action", None) or {}
    return action.get("sources", [])


def _count_web_search_calls(response: Any) -> int:
    return sum(1 for item in _iter_output_items(response) if _is_web_search_call(item))
