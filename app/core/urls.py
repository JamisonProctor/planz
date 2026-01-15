from urllib.parse import urlparse, urlunparse


def canonicalize_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""

    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    scheme = "https"
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    path = path.rstrip("/") or "/"

    rebuilt = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return rebuilt


def extract_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower()
