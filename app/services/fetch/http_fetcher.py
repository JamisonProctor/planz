import httpx


def fetch_url_text(url: str, timeout: float = 10.0) -> tuple[str | None, str | None, int | None]:
    headers = {"User-Agent": "PLAZN/0.1"}

    try:
        with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text, None, response.status_code
    except httpx.HTTPStatusError as exc:
        resp = exc.response
        status = resp.status_code if resp else None
        return None, str(exc), status
    except Exception as exc:  # noqa: BLE001
        return None, str(exc), None
