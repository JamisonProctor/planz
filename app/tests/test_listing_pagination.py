from app.services.fetch.listing_pagination import enumerate_listing_pages


PAGE1 = """
<html>
<body>
<a rel="next" href="https://example.com/page2">Weiter</a>
</body>
</html>
"""

PAGE2 = "<html><body>No next</body></html>"


def test_enumerate_listing_pages_follows_next(monkeypatch):
    pages = {
        "https://example.com/page1": PAGE1,
        "https://example.com/page2": PAGE2,
    }

    def fetcher(url: str, timeout: float = 10.0):
        return pages[url], None, 200

    urls = list(
        enumerate_listing_pages(
            start_url="https://example.com/page1",
            fetcher=fetcher,
            max_pages=5,
        )
    )
    assert urls == ["https://example.com/page1", "https://example.com/page2"]


def test_enumerate_listing_pages_stops_without_next(monkeypatch):
    def fetcher(url: str, timeout: float = 10.0):
        return PAGE2, None, 200

    urls = list(
        enumerate_listing_pages(
            start_url="https://example.com/page1",
            fetcher=fetcher,
            max_pages=5,
        )
    )
    assert urls == ["https://example.com/page1"]


def test_enumerate_listing_pages_stops_on_same_next() -> None:
    html = """
    <html><body><a rel="next" href="https://example.com/page1">Next</a></body></html>
    """

    def fetcher(url: str, timeout: float = 10.0):
        return html, None, 200

    urls = list(
        enumerate_listing_pages(
            start_url="https://example.com/page1",
            fetcher=fetcher,
            max_pages=5,
        )
    )
    assert urls == ["https://example.com/page1"]
