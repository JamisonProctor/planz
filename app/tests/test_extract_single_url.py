from datetime import datetime
from typing import Any

from app.scripts.extract_single_url import extract_single


def test_extract_single_uses_fetch_and_extractor(capsys) -> None:
    def fetcher(url: str, timeout: float = 10.0):
        return "<html><body>Event</body></html>", None, 200

    def extractor(text: str, source_url: str):
        return [
            {"title": "A", "start_time": datetime(2026, 1, 2).isoformat()},
            {"title": "B", "start_time": datetime(2026, 1, 3).isoformat()},
        ]

    summary = extract_single(
        url="https://example.com",
        fetcher=fetcher,
        extractor=extractor,
        persist=False,
    )

    captured = capsys.readouterr().out
    assert "extracted_events_count: 2" in captured
    assert summary["extracted_events_count"] == 2
    assert summary["http_status"] == 200
