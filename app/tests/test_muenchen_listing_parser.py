from app.services.extract.muenchen_listing_parser import parse_listing


HTML = """
<html><body>
<div class="card">
 <a href="/veranstaltungen/event/123">Event 1</a>
 <div class="address">Marienplatz 1</div>
</div>
<div class="card">
 <a href="https://www.muenchen.de/veranstaltungen/event/456">Event 2</a>
</div>
</body></html>
"""


def test_parse_listing_extracts_detail_and_address():
    events = parse_listing(HTML, base_url="https://www.muenchen.de/veranstaltungen/event/kinder")
    assert events[0]["detail_url"] == "https://www.muenchen.de/veranstaltungen/event/123"
    assert events[0]["address"] == "Marienplatz 1"
    assert events[1]["detail_url"] == "https://www.muenchen.de/veranstaltungen/event/456"
    assert events[1]["address"] is None
