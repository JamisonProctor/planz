import httpx

from app.services.fetch.http_fetcher import fetch_url_text


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, text: str | None = None, raise_error: Exception | None = None) -> None:
        self._text = text
        self._raise_error = raise_error
        self.headers = {}
        self.timeout = None
        self.follow_redirects = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str) -> _FakeResponse:
        if self._raise_error is not None:
            raise self._raise_error
        return _FakeResponse(self._text or "")


def test_fetch_url_text_success(monkeypatch) -> None:
    def fake_client(*args, **kwargs):
        return _FakeClient(text="ok")

    monkeypatch.setattr(httpx, "Client", fake_client)

    text, error, status = fetch_url_text("https://example.com")
    assert text == "ok"
    assert error is None
    assert status == 200


def test_fetch_url_text_error(monkeypatch) -> None:
    def fake_client(*args, **kwargs):
        return _FakeClient(raise_error=httpx.RequestError("boom", request=None))

    monkeypatch.setattr(httpx, "Client", fake_client)

    text, error, status = fetch_url_text("https://example.com")
    assert text is None
    assert error is not None
    assert status is None
