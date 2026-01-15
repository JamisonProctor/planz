import httpx


def fetch_url_text(url: str, timeout: float = 10.0) -> tuple[str | None, str | None]:
    headers = {"User-Agent": "PLAZN/0.1"}

    try:
        with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text, None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
