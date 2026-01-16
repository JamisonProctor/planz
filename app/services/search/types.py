from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResultItem:
    url: str
    title: str | None
    snippet: str | None
    rank: int
    domain: str
