from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def parse_listing(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    base_path = urlparse(base_url).path
    for link in soup.find_all("a", href=True):
        if _is_ticket_link(link):
            continue
        href = link["href"]
        detail_url = urljoin(base_url, href)
        parsed = urlparse(detail_url)
        if "/veranstaltungen/" not in parsed.path:
            continue
        if parsed.path == base_path:
            continue
        if detail_url in seen_urls:
            continue
        card = link.find_parent()
        address = None
        listing_text = None
        if card:
            addr_el = card.find(class_="address") or card.find(class_="location")
            if addr_el and addr_el.get_text(strip=True):
                address = addr_el.get_text(strip=True)
            text = card.get_text(" ", strip=True)
            if text:
                listing_text = text
        event: dict[str, Any] = {"detail_url": detail_url, "address": address}
        if listing_text:
            event["listing_text"] = listing_text
        ticket_url = _extract_ticket_url(card, base_url, detail_url) if card else None
        if ticket_url:
            event["ticket_url"] = ticket_url
        seen_urls.add(detail_url)
        events.append(event)
    return events


def _extract_ticket_url(card, base_url: str, detail_url: str) -> str | None:
    for link in card.find_all("a", href=True):
        candidate_url = urljoin(base_url, link["href"])
        if candidate_url == detail_url:
            continue
        if _is_ticket_link(link):
            return candidate_url
    return None


def _is_ticket_link(link) -> bool:
    attrs = [
        " ".join(link.get("class", [])),
        link.get("title", ""),
        link.get("aria-label", ""),
        link.get_text(" ", strip=True),
    ]
    haystack = " ".join(part.lower() for part in attrs if part)
    return "ticket" in haystack or "karten" in haystack
