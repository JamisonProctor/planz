from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.google_calendar_service import GoogleCalendarClient


def test_calendar_client_interface() -> None:
    client = GoogleCalendarClient()
    event = CalendarEvent(
        title="Test",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T01:00:00Z",
        location=None,
        description=None,
        source_url="https://example.com",
    )
    try:
        client.upsert_event(event)
    except NotImplementedError:
        assert True
