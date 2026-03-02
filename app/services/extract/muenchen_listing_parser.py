from __future__ import annotations

from datetime import date
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
    exact_events = _parse_muenchen_event_items(soup, base_url)
    if exact_events:
        return exact_events
    return _parse_generic_listing(soup, base_url)


def _parse_muenchen_event_items(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in soup.select(".m-event-list-item"):
        headline = item.select_one(".m-event-list-item__headline")
        if headline is None:
            continue
        title = headline.get_text(" ", strip=True)
        if not title:
            continue

        headline_link = headline.find("a", href=True)
        detail_url = None
        if headline_link is not None:
            detail_url = urljoin(base_url, headline_link["href"])

        location = None
        location_el = item.select_one('.m-event-list-item__detail[itemprop="location"]')
        if location_el is not None:
            location = location_el.get_text(" ", strip=True) or None

        detail_block = _find_calendar_detail_block(item)
        raw_schedule = None
        start_time = None
        end_time = None
        if detail_block is not None:
            raw_schedule = _normalize_schedule_text(detail_block)
            start_time, end_time = _parse_detail_times(detail_block)

        ticket_url = _extract_ticket_url(item, base_url, detail_url)
        range_start, range_end = _extract_date_range(item)

        dedupe_key = "|".join(
            [
                detail_url or ticket_url or title,
                start_time or "",
                ticket_url or "",
            ]
        )
        if dedupe_key in seen_keys:
            continue

        event: dict[str, Any] = {
            "title": title,
            "address": location,
            "location": location,
            "listing_text": item.get_text(" ", strip=True),
        }
        if detail_url:
            event["detail_url"] = detail_url
        if raw_schedule:
            event["raw_schedule"] = raw_schedule
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if ticket_url:
            event["ticket_url"] = ticket_url
        if range_start:
            event["range_start_date"] = range_start.isoformat()
        if range_end:
            event["range_end_date"] = range_end.isoformat()
        seen_keys.add(dedupe_key)
        events.append(event)
    return events


def _parse_generic_listing(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
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
        if detail_url and candidate_url == detail_url:
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
    scheduled_candidate = None
    while current is not None:
        classes = current.get("class", [])
        if isinstance(classes, list) and "card" in classes:
            return current
        text = current.get_text(" ", strip=True)
        if text and _extract_schedule(text):
            scheduled_candidate = current
        elif text and (
            current.find(class_="address") is not None
            or current.find(class_="location") is not None
        ):
            scheduled_candidate = current
        current = current.parent
    return scheduled_candidate or fallback


def _find_calendar_detail_block(item):
    for detail in item.select(".m-event-list-item__detail"):
        if detail.find("time") is not None:
            return detail
    return None


def _parse_detail_times(detail_block) -> tuple[str | None, str | None]:
    time_tags = detail_block.find_all("time")
    if not time_tags:
        return None, None
    start_time = _parse_display_datetime(time_tags[0].get("datetime"))
    end_time = None
    if len(time_tags) > 1:
        end_time = _parse_display_datetime(time_tags[1].get("datetime"))
    return start_time, end_time


def _parse_display_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value.strip(), "%d.%m.%Y - %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=ZoneInfo("Europe/Berlin")).isoformat()


def _normalize_schedule_text(detail_block) -> str | None:
    text = " ".join(detail_block.stripped_strings)
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" - ", " - ")
    if text.endswith("Uhr") or "Uhr" in text:
        return text
    if re.search(r"\d{2}:\d{2}$", text):
        return f"{text} Uhr"
    return text


def _extract_date_range(item) -> tuple[date | None, date | None]:
    time_tags = item.select(".m-date-range time.m-date-range__item[datetime]")
    if not time_tags:
        return None, None
    start_date = _parse_range_date(time_tags[0].get("datetime"))
    end_date = start_date
    if len(time_tags) > 1:
        end_date = _parse_range_date(time_tags[1].get("datetime")) or start_date
    return start_date, end_date


def _parse_range_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
