from app.services.fetch.diagnostics import (
    contains_date_token,
    contains_event_list_marker,
)


def test_contains_date_token_matches_formats() -> None:
    assert contains_date_token("Event on 12.03.2026")
    assert contains_date_token("Event on 2026-04-05")
    assert contains_date_token("Sa. Workshop")
    assert contains_date_token("So. Konzert")


def test_contains_event_list_marker_counts_repeats() -> None:
    html = "<div class='event-card'>A</div><div class='event__item'>B</div>"
    assert contains_event_list_marker(html)


def test_contains_event_list_marker_false_when_sparse() -> None:
    html = "<div class='event-card'>A</div>"
    assert contains_event_list_marker(html) is False
