from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    search_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_runs.id")
    )
    language: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
    )

    run: Mapped["SearchRun"] = relationship(back_populates="queries")
    results: Mapped[list["SearchResult"]] = relationship(back_populates="query")
