from app.core.urls import canonicalize_url, extract_domain


def test_canonicalize_url_adds_https_and_strips_whitespace() -> None:
    assert canonicalize_url(" example.com/path ") == "https://example.com/path"


def test_canonicalize_url_removes_fragment_and_preserves_query() -> None:
    assert (
        canonicalize_url("https://example.com/path?x=1#section")
        == "https://example.com/path?x=1"
    )


def test_canonicalize_url_removes_trailing_slash_except_root() -> None:
    assert canonicalize_url("https://example.com/path/") == "https://example.com/path"
    assert canonicalize_url("https://example.com/") == "https://example.com/"


def test_extract_domain_lowercases_and_handles_missing_scheme() -> None:
    assert extract_domain("https://Example.COM/Path") == "example.com"
    assert extract_domain("Example.COM/path") == "example.com"
