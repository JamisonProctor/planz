from __future__ import annotations

import asyncio
import os
from typing import Optional

try:
    from playwright.async_api import async_playwright as _async_playwright
except ImportError:  # pragma: no cover - optional dependency
    _async_playwright = None


def is_allowlisted(domain: str) -> bool:
    allowlist = os.getenv("PLANZ_PLAYWRIGHT_ALLOWLIST", "www.muenchen.de,muenchen.de")
    domains = {item.strip().lower() for item in allowlist.split(",") if item.strip()}
    return domain.lower() in domains


def fetch_url_playwright(
    url: str, timeout: float = 10.0
) -> tuple[str | None, str | None, Optional[int]]:
    async def _run() -> tuple[str | None, str | None, Optional[int]]:
        if _async_playwright is None:
            return None, "playwright_not_installed", None

        try:
            async with _async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto(
                    url, wait_until="networkidle", timeout=timeout * 1000
                )
                content = await page.content()
                status = response.status if response else None
                await browser.close()
                return content, None, status
        except Exception as exc:  # noqa: BLE001
            return None, str(exc), None

    return asyncio.run(_run())
