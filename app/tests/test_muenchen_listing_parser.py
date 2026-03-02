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

OCCURRENCE_HTML = """
<html><body>
<div class="card">
 <a href="/veranstaltungen/ausstellungen/kinder/der-gasteig-brummt">Der Gasteig brummt</a>
 <div>Fr. 06.03.2026 09:00 - 11:00 Uhr</div>
 <div class="location">Gasteig HP8</div>
 <a class="ticket-icon" href="https://tickets.example.com/gasteig" title="Tickets">Tickets</a>
</div>
<div class="card">
 <a href="/veranstaltungen/ausstellungen/kinder/der-gasteig-brummt">Der Gasteig brummt</a>
 <div>Sa. 07.03.2026 09:00 - 11:00 Uhr</div>
 <div class="location">Gasteig HP8</div>
 <a class="ticket-icon" href="https://tickets.example.com/gasteig" title="Tickets">Tickets</a>
</div>
</body></html>
"""

NESTED_CARD_HTML = """
<html><body>
<div class="card">
 <h3><a href="/veranstaltungen/ausstellungen/kinder/der-gasteig-brummt">Der Gasteig brummt</a></h3>
 <div>Fr. 06.03.2026 09:00 - 11:00 Uhr</div>
 <div class="location">Gasteig HP8</div>
</div>
</body></html>
"""


def test_parse_listing_extracts_detail_and_address():
    events = parse_listing(HTML, base_url="https://www.muenchen.de/veranstaltungen/event/kinder")
    assert events[0]["detail_url"] == "https://www.muenchen.de/veranstaltungen/event/123"
    assert events[0]["address"] == "Marienplatz 1"
    assert "Event 1" in events[0]["listing_text"]
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
            "title": "Kindheit am Nil",
            "listing_text": "Kindheit am Nil Museum",
            "location": "Museum",
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
            "title": "Kindheit am Nil",
            "listing_text": "Kindheit am Nil Buy Museum",
            "ticket_url": "https://tickets.example.com/kindheit-am-nil",
            "location": "Museum",
        }
    ]


def test_parse_listing_extracts_structured_occurrences_without_deduping_same_detail_url() -> None:
    events = parse_listing(
        OCCURRENCE_HTML,
        base_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert len(events) == 2
    assert events[0]["detail_url"] == events[1]["detail_url"]
    assert events[0]["title"] == "Der Gasteig brummt"
    assert events[0]["location"] == "Gasteig HP8"
    assert events[0]["ticket_url"] == "https://tickets.example.com/gasteig"
    assert events[0]["raw_schedule"] == "Fr. 06.03.2026 09:00 - 11:00 Uhr"
    assert events[0]["start_time"] == "2026-03-06T09:00:00+01:00"
    assert events[0]["end_time"] == "2026-03-06T11:00:00+01:00"
    assert events[1]["raw_schedule"] == "Sa. 07.03.2026 09:00 - 11:00 Uhr"


def test_parse_listing_finds_schedule_from_ancestor_card() -> None:
    events = parse_listing(
        NESTED_CARD_HTML,
        base_url="https://www.muenchen.de/veranstaltungen/event/kinder",
    )

    assert len(events) == 1
    assert events[0]["title"] == "Der Gasteig brummt"
    assert events[0]["raw_schedule"] == "Fr. 06.03.2026 09:00 - 11:00 Uhr"
    assert events[0]["location"] == "Gasteig HP8"
