from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Callable

from app.core.urls import canonicalize_url, extract_domain
from app.services.discovery.source_policies import is_domain_allowed
from app.services.fetch.http_fetcher import fetch_url_text

logger = logging.getLogger(__name__)

MIN_TEXT_LEN = 1500
DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", re.IGNORECASE),
    re.compile(r"\b(Januar|Februar|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\b", re.IGNORECASE),
]
ARCHIVE_SIGNALS = ["archiv", "rueckblick", "ruckblick"]
JS_SIGNALS = ["enable javascript", "javascript required"]


def _has_date_token(text: str) -> bool:
    return any(pattern.search(text) for pattern in DATE_PATTERNS)


def _has_archive_signal(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in ARCHIVE_SIGNALS)


def _has_past_year(text: str, current_year: int) -> bool:
    for token in text.split():
        if token.isdigit() and len(token) == 4:
            try:
                year = int(token)
            except ValueError:
                continue
            if year < current_year:
                return True
    return False


def _is_js_suspected(text: str) -> bool:
    lower = text.lower()
    if any(token in lower for token in JS_SIGNALS):
        return True

    tag_stripped = re.sub(r"<[^>]+>", " ", text)
    visible_len = len(tag_stripped.strip())
    total_len = len(text.strip())
    if total_len == 0:
        return False

    ratio = visible_len / total_len
    script_count = len(re.findall(r"<script", lower))
    return ratio < 0.2 or script_count > 10


def verify_candidate_url(
    url: str,
    fetcher: Callable[[str, float], tuple[str | None, str | None]] = fetch_url_text,
    min_text_len: int = MIN_TEXT_LEN,
) -> tuple[bool, str, str | None, int | None]:
    canonical = canonicalize_url(url)
    if not canonical:
        return False, "fetch_failed", None, None

    domain = extract_domain(canonical)
    if not is_domain_allowed(domain):
        return False, "blocked_domain", canonical, None

    text, error = fetcher(canonical, 5.0)
    if error or text is None:
        return False, "fetch_failed", canonical, None

    content_length = len(text)
    if content_length < min_text_len:
        return False, "too_short", canonical, content_length

    if _has_archive_signal(text) or _has_past_year(text, datetime.utcnow().year):
        return False, "archive_signals", canonical, content_length

    if _is_js_suspected(text):
        return False, "js_suspected", canonical, content_length

    if not _has_date_token(text):
        return False, "no_date_tokens", canonical, content_length

    return True, "accepted", canonical, content_length
