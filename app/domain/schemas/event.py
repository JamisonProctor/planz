from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventDraft(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    source_url: str
    summary: str | None = None
    flags: dict[str, Any] = Field(default_factory=dict)


class EventNormalized(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    source_url: str
    summary: str | None = None
    flags: dict[str, Any] = Field(default_factory=dict)
