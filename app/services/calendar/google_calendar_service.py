import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.base import CalendarClient
from app.core.urls import extract_domain

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "Europe/Berlin"


class GoogleCalendarClient(CalendarClient):
    def __init__(self, calendar_id: str | None = None) -> None:
        self.calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
        self._disabled = bool(os.getenv("PYTEST_CURRENT_TEST"))
        self.service = None if self._disabled else self._get_calendar_service()

    def upsert_event(self, calendar_event: CalendarEvent) -> str:
        if self._disabled:
            raise NotImplementedError("Google Calendar calls are disabled in tests.")
        event_body = self._build_event_body(calendar_event)
        event_id = getattr(calendar_event, "google_event_id", None)

        try:
            if event_id:
                response = (
                    self.service.events()
                    .update(calendarId=self.calendar_id, eventId=event_id, body=event_body)
                    .execute()
                )
                return response["id"]

            response = (
                self.service.events()
                .insert(calendarId=self.calendar_id, body=event_body)
                .execute()
            )
            return response["id"]
        except HttpError as exc:
            logger.error("Google Calendar upsert failed: %s", exc, exc_info=True)
            raise

    def delete_event(self, calendar_event_id: str) -> None:
        """Delete event by ID; raises HttpError on failure (including missing IDs)."""
        if self._disabled:
            raise NotImplementedError("Google Calendar calls are disabled in tests.")
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=calendar_event_id,
            ).execute()
        except HttpError as exc:
            logger.error("Google Calendar delete failed: %s", exc, exc_info=True)
            raise

    def _get_calendar_service(self):
        token_path = Path(settings.GOOGLE_TOKEN_PATH)
        if not token_path.exists():
            raise FileNotFoundError(
                "Missing Google OAuth token file at "
                f"{settings.GOOGLE_TOKEN_PATH}. Run the OAuth flow to generate it."
            )

        creds = Credentials.from_authorized_user_file(settings.GOOGLE_TOKEN_PATH, SCOPES)
        return build("calendar", "v3", credentials=creds)

    @staticmethod
    def _build_event_body(calendar_event: CalendarEvent) -> dict[str, Any]:
        summary = calendar_event.title

        description_parts = []
        if calendar_event.description:
            description_parts.append(calendar_event.description)
        else:
            description_parts.append(summary)
        if calendar_event.source_url:
            description_parts.append(f"More info: {calendar_event.source_url}")

        body: dict[str, Any] = {
            "summary": summary,
            "start": {
                "dateTime": calendar_event.start.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": calendar_event.end.isoformat(),
                "timeZone": TIMEZONE,
            },
        }
        domain = extract_domain(calendar_event.source_url) if getattr(calendar_event, "source_url", None) else ""
        planz_key = calendar_event.external_key or f"{calendar_event.title}:{calendar_event.start.isoformat()}"
        body["extendedProperties"] = {
            "private": {
                "planz": "true",
                "planz_source": domain or "unknown",
                "planz_key": planz_key,
            }
        }

        if calendar_event.source_url:
            body["source"] = {
                "title": domain or "source",
                "url": calendar_event.source_url,
            }

        if calendar_event.location:
            body["location"] = calendar_event.location
        if description_parts:
            body["description"] = "\n\n".join(description_parts)

        return body
