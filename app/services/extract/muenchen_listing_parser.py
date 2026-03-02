from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

_SCHEDULE_RE = re.compile(
    r"((?:Mo|Di|Mi|Do|Fr|Sa|So)\.\s+\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}(?:\s*-\s*\d{2}:\d{2})?\s*Uhr)"
)


def parse_listing(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
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
        card = _find_listing_card(link)
        address = None
        listing_text = None
        if card:
            addr_el = card.find(class_="address") or card.find(class_="location")
            if addr_el and addr_el.get_text(strip=True):
                address = addr_el.get_text(strip=True)
            text = card.get_text(" ", strip=True)
            if text:
                listing_text = text
        dedupe_key = f"{detail_url}|{listing_text or ''}"
        if dedupe_key in seen_keys:
            continue
        event: dict[str, Any] = {"detail_url": detail_url, "address": address}
        title = link.get_text(" ", strip=True)
        if title:
            event["title"] = title
        if listing_text:
            event["listing_text"] = listing_text
            schedule = _extract_schedule(listing_text)
            if schedule:
                event["raw_schedule"] = schedule
                start_time, end_time = _parse_schedule(schedule)
                if start_time:
                    event["start_time"] = start_time
                if end_time:
                    event["end_time"] = end_time
        ticket_url = _extract_ticket_url(card, base_url, detail_url) if card else None
        if ticket_url:
            event["ticket_url"] = ticket_url
        if address:
            event["location"] = address
        seen_keys.add(dedupe_key)
        events.append(event)
    return events


def _extract_schedule(listing_text: str) -> str | None:
    match = _SCHEDULE_RE.search(listing_text)
    if not match:
        return None
    return match.group(1)


def _parse_schedule(schedule: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"(?:Mo|Di|Mi|Do|Fr|Sa|So)\.\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})(?:\s*-\s*(\d{2}):(\d{2}))?\s*Uhr",
        schedule,
    )
    if not match:
        return None, None
    day, month, year, start_h, start_m, end_h, end_m = match.groups()
    tz = ZoneInfo("Europe/Berlin")
    start_dt = datetime(
        int(year), int(month), int(day), int(start_h), int(start_m), tzinfo=tz
    )
    end_dt = None
    if end_h and end_m:
        end_dt = datetime(
            int(year), int(month), int(day), int(end_h), int(end_m), tzinfo=tz
        )
    return start_dt.isoformat(), end_dt.isoformat() if end_dt else None


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


def _find_listing_card(link):
    current = link.parent
    fallback = current
    while current is not None:
        classes = current.get("class", [])
        if isinstance(classes, list) and "card" in classes:
            return current
        current = current.parent
    return fallback
