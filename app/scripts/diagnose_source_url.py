from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.env import load_env
from app.logging import configure_logging
from app.services.fetch.diagnostics import (
    contains_date_token,
    contains_event_list_marker,
)
from app.services.fetch.playwright_fetcher import fetch_url_playwright, is_allowlisted
from app.core.urls import extract_domain


@dataclass
class FetchResult:
    text: Optional[str]
    error: Optional[str]
    status: Optional[int]
    final_url: Optional[str]
    content_type: Optional[str]


def _plain_fetch(url: str, timeout: float = 10.0) -> FetchResult:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            return FetchResult(
                text=response.text,
                error=None,
                status=response.status_code,
                final_url=str(response.url),
                content_type=response.headers.get("content-type"),
            )
    except httpx.HTTPStatusError as exc:
        resp = exc.response
        return FetchResult(
            text=None,
            error=str(exc),
            status=resp.status_code if resp else None,
            final_url=str(resp.url) if resp else None,
            content_type=resp.headers.get("content-type") if resp else None,
        )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(text=None, error=str(exc), status=None, final_url=None, content_type=None)


def _print_report(label: str, result: FetchResult) -> None:
    content_len = len(result.text) if result.text else 0
    print(f"[{label}] status={result.status} length={content_len} type={result.content_type} url_final={result.final_url}")
    if result.text:
        print(
            f"  contains_date_token={contains_date_token(result.text)} "
            f"contains_event_list_marker={contains_event_list_marker(result.text)}"
        )
    if result.error:
        print(f"  error={result.error}")


def main() -> None:
    load_env()
    configure_logging()
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.diagnose_source_url <url>")
        sys.exit(1)

    url = sys.argv[1]
    plain = _plain_fetch(url)
    _print_report("plain", plain)

    use_playwright = os.getenv("PLANZ_USE_PLAYWRIGHT", "").strip().lower() in {"true", "1", "yes"}
    domain = extract_domain(url)
    if use_playwright and is_allowlisted(domain):
        pw_text, pw_err, pw_status = fetch_url_playwright(url)
        pw_result = FetchResult(
            text=pw_text,
            error=pw_err,
            status=pw_status,
            final_url=url,
            content_type=None,
        )
        _print_report("playwright", pw_result)


if __name__ == "__main__":
    main()
