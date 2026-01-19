import types

from app.services.fetch.playwright_fetcher import fetch_url_playwright


class _DummyResponse:
    def __init__(self):
        self.status = 200
        self.url = "https://example.com/final"


class _DummyPage:
    def __init__(self, response):
        self._response = response
        self.content_called = False
        self.goto_called = False

    async def goto(self, url, wait_until=None, timeout=None):
        self.goto_called = True
        return self._response

    async def content(self):
        self.content_called = True
        return "<html>ok</html>"


class _DummyBrowser:
    def __init__(self, page):
        self._page = page
        self.closed = False

    async def new_page(self):
        return self._page

    async def close(self):
        self.closed = True


class _DummyContext:
    def __init__(self, browser):
        self._browser = browser

    async def __aenter__(self):
        return types.SimpleNamespace(chromium=self)

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def launch(self, headless=True):
        return self._browser


def test_playwright_fetcher_uses_goto(monkeypatch):
    response = _DummyResponse()
    page = _DummyPage(response)
    browser = _DummyBrowser(page)
    ctx = _DummyContext(browser)

    monkeypatch.setattr(
        "app.services.fetch.playwright_fetcher._async_playwright", lambda: ctx
    )

    content, err, status = fetch_url_playwright("https://example.com")

    assert err is None
    assert status == 200
    assert content == "<html>ok</html>"
    assert page.goto_called is True
    assert page.content_called is True
