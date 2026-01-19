import types

from app.scripts.calendar_wipe_planz import is_planz_event, filter_planz_events
from app.scripts import calendar_wipe_planz
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpMock


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


class _DummyDelete:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def execute(self):
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


class _DummyEventsService:
    def __init__(self, responses):
        self._responses = responses

    def list(self, **kwargs):
        return types.SimpleNamespace(execute=lambda: {"items": [{"id": "1", "summary": "s"}]})

    def delete(self, calendarId, eventId):
        return _DummyDelete(self._responses)


class _DummyClient:
    def __init__(self, responses):
        self.service = self
        self._responses = responses
        self.calendar_id = "cal"

    def events(self):
        return _DummyEventsService(self._responses)


def _rate_limit_error():
    mock = HttpMock(headers={"status": "403", "reason": "rateLimitExceeded"})
    mock.status = 403
    mock.reason = "rateLimitExceeded"
    return HttpError(resp=mock, content=b"rateLimitExceeded")


def _generic_error():
    mock = HttpMock(headers={"status": "400", "reason": "generic"})
    mock.status = 400
    mock.reason = "generic"
    return HttpError(resp=mock, content=b"generic")


def test_wipe_retries_rate_limit(monkeypatch):
    client = _DummyClient([_rate_limit_error(), "ok"])
    monkeypatch.setattr(calendar_wipe_planz, "filter_planz_events", lambda events, force_legacy=False: [{"id": "1", "summary": "s"}])
    monkeypatch.setattr(calendar_wipe_planz.time, "sleep", lambda *args, **kwargs: None)
    calendar_wipe_planz.wipe_planz_events(client, days=1, dry_run=False, force_legacy=False)


def test_wipe_counts_failures(monkeypatch):
    client = _DummyClient([_generic_error(), "ok"])
    monkeypatch.setattr(calendar_wipe_planz, "filter_planz_events", lambda events, force_legacy=False: [{"id": "1", "summary": "s"}, {"id": "2", "summary": "s"}])
    monkeypatch.setattr(calendar_wipe_planz.time, "sleep", lambda *args, **kwargs: None)
    calendar_wipe_planz.wipe_planz_events(client, days=1, dry_run=False, force_legacy=False)


def test_is_planz_event_force_legacy() -> None:
    event = {"summary": "[PLZ] Old"}
    assert is_planz_event(event, force_legacy=True) is True
