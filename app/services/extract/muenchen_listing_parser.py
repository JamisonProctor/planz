from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_listing(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict[str, Any]] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/veranstaltungen/event/" not in href:
            continue
        detail_url = urljoin(base_url, href)
        card = link.find_parent()
        address = None
        if card:
            addr_el = card.find(class_="address") or card.find(class_="location")
            if addr_el and addr_el.get_text(strip=True):
                address = addr_el.get_text(strip=True)
        events.append({"detail_url": detail_url, "address": address})
    return events
