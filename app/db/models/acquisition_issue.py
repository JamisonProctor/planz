from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.search_result import SearchResult


class AwareDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class AcquisitionIssue(Base):
    __tablename__ = "acquisition_issues"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    url: Mapped[str] = mapped_column(Text, unique=True)
    domain: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        AwareDateTime(),
        default=lambda: datetime.now(tz=timezone.utc),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        AwareDateTime(),
        default=lambda: datetime.now(tz=timezone.utc),
    )
    reason: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discovered_search_result_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_results.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    search_result: Mapped["SearchResult"] = relationship()
