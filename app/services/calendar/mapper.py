from app.db.models.event import Event
from app.domain.schemas.calendar import CalendarEvent


def event_to_calendar_event(event: Event) -> CalendarEvent:
    return CalendarEvent(
        title=event.title,
        start=event.start_time,
        end=event.end_time,
        location=event.location,
        description=event.description,
        source_url=event.source_url,
        external_key=event.external_key,
        google_event_id=event.google_event_id,
    )
