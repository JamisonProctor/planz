from app.scripts.calendar_wipe_planz import is_planz_event, filter_planz_events


def test_is_planz_event_matches_prefix() -> None:
    event = {"summary": "[PLZ] Kids"}
    assert is_planz_event(event) is False
    assert is_planz_event(event, force_legacy=True) is True


def test_is_planz_event_matches_private_prop() -> None:
    event = {"summary": "Kids", "extendedProperties": {"private": {"planz": "true"}}}
    assert is_planz_event(event) is True


def test_is_planz_event_ignores_others() -> None:
    event = {"summary": "Kids"}
    assert is_planz_event(event) is False


def test_filter_planz_events() -> None:
    events = [
        {"summary": "[PLZ] A"},
        {"summary": "B", "extendedProperties": {"private": {"planz": "true"}}},
        {"summary": "C"},
    ]
    marked = filter_planz_events(events)
    assert len(marked) == 1
    marked_legacy = filter_planz_events(events, force_legacy=True)
    assert len(marked_legacy) == 2


def test_is_planz_event_force_legacy() -> None:
    event = {"summary": "[PLZ] Old"}
    assert is_planz_event(event, force_legacy=True) is True
