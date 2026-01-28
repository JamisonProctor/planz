import logging
import os
from pathlib import Path
import random
import time
from typing import Any
from urllib.parse import quote_plus

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.domain.schemas.calendar import CalendarEvent
from app.services.calendar.base import CalendarClient
from app.core.urls import extract_domain
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "Europe/Berlin"


class GoogleCalendarClient(CalendarClient):
    def __init__(
        self,
        calendar_id: str | None = None,
        service=None,
        allow_in_tests: bool = False,
    ) -> None:
        self.calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
        self._disabled = bool(os.getenv("PYTEST_CURRENT_TEST")) and not allow_in_tests
        self.service = service if service is not None else (None if self._disabled else self._get_calendar_service())

    def upsert_event(self, calendar_event: CalendarEvent) -> str:
        if self._disabled:
            raise NotImplementedError("Google Calendar calls are disabled in tests.")
        event_body = self._build_event_body(calendar_event)
        event_id = getattr(calendar_event, "google_event_id", None)

        attempts = 5
        backoff = 0.5
        for attempt in range(1, attempts + 1):
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
                if self._is_rate_limited(exc) and attempt < attempts:
                    sleep_for = backoff * (2 ** (attempt - 1)) * (1 + random.random() * 0.1)
                    time.sleep(sleep_for)
                    continue
                logger.error(
                    "Google Calendar upsert failed: %s",
                    exc,
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                raise

    def find_event_by_key(self, external_key: str, calendar_event: CalendarEvent | None = None) -> str | None:
        if self._disabled:
            return None
        time_min, time_max = _build_time_window(calendar_event)
        if not time_min or not time_max:
            logger.error(
                "Skipping find_event_by_key for key=%s due to invalid time window",
                external_key,
            )
            return None
        try:
            result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    privateExtendedProperty=[f"planz_key={external_key}"],
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    maxResults=2,
                )
                .execute()
            )
        except HttpError as exc:
            logger.error(
                "Google Calendar list failed for key=%s: %s",
                external_key,
                exc,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            return None

        items = result.get("items", []) if isinstance(result, dict) else []
        return items[0]["id"] if items else None

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
            logger.error(
                "Google Calendar delete failed: %s",
                exc,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
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

    @staticmethod
    def _is_rate_limited(exc: HttpError) -> bool:
        try:
            reason = exc.error_details[0].get("reason") if exc.error_details else None
            if reason == "rateLimitExceeded":
                return True
        except Exception:
            pass
        return getattr(exc.resp, "status", None) == 403


def _build_time_window(calendar_event: CalendarEvent | None) -> tuple[str | None, str | None]:
    now = datetime.now(tz=timezone.utc)
    if calendar_event is None:
        start = now - timedelta(days=1)
        end = now + timedelta(days=365)
    else:
        start = calendar_event.start
        end = calendar_event.end
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        is_all_day = (
            start.hour == 0
            and start.minute == 0
            and start.second == 0
            and end.hour == 0
            and end.minute == 0
            and end.second == 0
        )
        if is_all_day:
            start = datetime(start.year, start.month, start.day, tzinfo=start.tzinfo)
            end = start + timedelta(days=1)
        else:
            if end <= start:
                end = start + timedelta(hours=1)
            start = start - timedelta(hours=12)
            end = max(end, start + timedelta(hours=1))

    if end <= start:
        return None, None
    return start.isoformat(), end.isoformat()
