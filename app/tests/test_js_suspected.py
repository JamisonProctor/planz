from app.services.search.verify_sources import _is_js_suspected


def test_js_suspected_keyword() -> None:
    html = "<html><body>Enable JavaScript to view this page.</body></html>"
    assert _is_js_suspected(html) is True


def test_js_suspected_low_text_ratio() -> None:
    html = "<html>" + ("<script>var x=1;</script>" * 20) + "<body>Hi</body></html>"
    assert _is_js_suspected(html) is True
