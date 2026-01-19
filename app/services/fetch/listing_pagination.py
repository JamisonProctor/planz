from __future__ import annotations

import hashlib
import os
from typing import Callable, Iterator

from bs4 import BeautifulSoup

from app.core.urls import canonicalize_url


def enumerate_listing_pages(
    start_url: str,
    fetcher: Callable[[str, float], tuple[str | None, str | None, int | None]],
    max_pages: int | None = None,
) -> Iterator[str]:
    max_pages = max_pages or int(os.getenv("PLANZ_MAX_LISTING_PAGES", "10"))
    seen = set()
    current = start_url
    previous_hash = None
    for _ in range(max_pages):
        if current in seen:
            break
        seen.add(current)
        yield current
        text, error, status = fetcher(current, 10.0)
        if error or text is None:
            break
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        if previous_hash is not None and previous_hash == content_hash:
            break
        previous_hash = content_hash
        soup = BeautifulSoup(text, "html.parser")
        next_link = soup.find("a", rel="next")
        if not next_link or not next_link.get("href"):
            break
        next_url = canonicalize_url(next_link["href"])
        if not next_url:
            break
        if next_url == current:
            break
        current = next_url
