from app.services.search.query_bundle import build_query_bundle


def test_query_bundle_includes_languages_and_terms() -> None:
    queries = build_query_bundle(location="Munich, Germany", window_days=30)
    joined = " ".join(item["query"] for item in queries)

    assert len(queries) >= 8
    assert "kostenlos" in joined
    assert "free" in joined
    assert "München" in joined
    assert "Munich" in joined

    languages = {item["language"] for item in queries}
    assert "de" in languages
    assert "en" in languages
