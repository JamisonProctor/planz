from __future__ import annotations

from bs4 import BeautifulSoup


class HtmlToText:
    def extract(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        return " ".join(text.split())
