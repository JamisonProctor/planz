from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    search_query_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_queries.id")
    )
    rank: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
    )

    query: Mapped["SearchQuery"] = relationship(back_populates="results")
    discoveries: Mapped[list["SourceUrlDiscovery"]] = relationship(
        back_populates="search_result"
    )
