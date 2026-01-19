from __future__ import annotations

import re


DATE_REGEXES = [
    re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b"),  # German style
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # ISO
    re.compile(r"\bSa\.", re.IGNORECASE),
    re.compile(r"\bSo\.", re.IGNORECASE),
]

EVENT_MARKER_REGEX = re.compile(
    r"(event-card|event__item|event-list|veranstaltung|event-row|eventitem)",
    re.IGNORECASE,
)


def contains_date_token(text: str) -> bool:
    return any(regex.search(text) for regex in DATE_REGEXES)


def contains_event_list_marker(text: str, min_matches: int = 2) -> bool:
    matches = EVENT_MARKER_REGEX.findall(text)
    return len(matches) >= min_matches
