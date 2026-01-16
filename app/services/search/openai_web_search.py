from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from app.core.urls import extract_domain
from app.services.search.base import SearchProvider
from app.services.search.types import SearchResultItem


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
        response = self._client.responses.create(
            model="gpt-4o-mini",
            input=query,
            tools=[{"type": "web_search"}],
            tool_choice={"type": "web_search"},
        )

        results: list[SearchResultItem] = []
        raw_items = _extract_search_results(response)
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
    output = getattr(response, "output", None)
    if not output:
        return []

    results: list[dict[str, Any]] = []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "web_search":
            results.extend(item.get("results", []))
        elif getattr(item, "type", None) == "web_search":
            results.extend(getattr(item, "results", []))

    return results
