from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.event import Event


class CalendarSync(Base):
    __tablename__ = "calendar_syncs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("events.id"),
        unique=True,
    )
    provider: Mapped[str] = mapped_column(String(50), default="google")
    calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship(back_populates="calendar_sync")
