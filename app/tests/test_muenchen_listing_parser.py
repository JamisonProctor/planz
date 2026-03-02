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

DETAIL_VARIANT_HTML = """
<html><body>
<div class="card">
 <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
 <div class="location">Museum</div>
</div>
<a href="/veranstaltungen/event/kinder?page=2">Next</a>
</body></html>
"""

TICKET_HTML = """
<html><body>
<div class="card">
 <a href="/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum">Kindheit am Nil</a>
 <a class="ticket-icon" href="https://tickets.example.com/kindheit-am-nil" title="Tickets">Buy</a>
 <div class="location">Museum</div>
</div>
</body></html>
"""


def test_parse_listing_extracts_detail_and_address():
    events = parse_listing(HTML, base_url="https://www.muenchen.de/veranstaltungen/event/kinder")
    assert events[0]["detail_url"] == "https://www.muenchen.de/veranstaltungen/event/123"
    assert events[0]["address"] == "Marienplatz 1"
    assert events[1]["detail_url"] == "https://www.muenchen.de/veranstaltungen/event/456"
    assert events[1]["address"] is None


def test_parse_listing_includes_nested_event_paths_and_skips_pagination() -> None:
    events = parse_listing(
        DETAIL_VARIANT_HTML,
        base_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert events == [
        {
            "detail_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "address": "Museum",
        }
    ]


def test_parse_listing_extracts_ticket_link_from_card() -> None:
    events = parse_listing(
        TICKET_HTML,
        base_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert events == [
        {
            "detail_url": "https://www.muenchen.de/veranstaltungen/ausstellungen/kinder/kindheit-am-nil-aegyptisches-museum",
            "address": "Museum",
            "ticket_url": "https://tickets.example.com/kindheit-am-nil",
        }
    ]
