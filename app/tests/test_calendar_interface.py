from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.google_calendar_service import GoogleCalendarClient


def test_calendar_client_interface() -> None:
    # Interface presence test; no network call
    body = GoogleCalendarClient._build_event_body(
        CalendarEvent(
            title="Test",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T01:00:00Z",
            location=None,
            description=None,
            source_url="https://example.com",
        )
    )
    assert body["summary"] == "Test"
    if "location" in body:
        assert "http" not in (body.get("location") or "")
    assert body["extendedProperties"]["private"]["planz"] == "true"
    assert body["source"]["url"] == "https://example.com"
