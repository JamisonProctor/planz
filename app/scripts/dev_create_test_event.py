from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.google_calendar_service import GoogleCalendarClient


def main() -> None:
    tz = ZoneInfo("Europe/Berlin")
    start = datetime.now(tz=tz) + timedelta(hours=1)
    end = start + timedelta(hours=1)

    event = CalendarEvent(
        title="PLANZ Test Event",
        start=start,
        end=end,
        location="Marienplatz, München",
        description="Test event created by PLANZ dev script.",
        source_url="https://example.com",
    )

    client = GoogleCalendarClient(calendar_id=settings.GOOGLE_CALENDAR_ID)
    event_id = client.upsert_event(event)
    print(event_id)


if __name__ == "__main__":
    main()
