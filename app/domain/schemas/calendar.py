from datetime import datetime

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
    source_url: str | None = None
    google_event_id: str | None = None
