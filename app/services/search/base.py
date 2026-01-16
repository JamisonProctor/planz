from __future__ import annotations

from typing import Protocol

from app.services.search.types import SearchResultItem


class SearchProvider(Protocol):
    def search(
        self,
        query: str,
        language: str,
        location: str,
        max_results: int,
    ) -> list[SearchResultItem]:
        ...
