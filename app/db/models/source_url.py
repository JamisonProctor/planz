from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.source_domain import SourceDomain
    from app.db.models.source_url_discovery import SourceUrlDiscovery


class SourceUrl(Base):
    __tablename__ = "source_urls"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    domain_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source_domains.id"),
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fetch_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_extracted_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_extraction_count: Mapped[int | None] = mapped_column(nullable=True)
    last_extraction_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_method: Mapped[str] = mapped_column(String(50), default="llm_search")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    domain: Mapped[SourceDomain] = relationship(back_populates="urls")
    discoveries: Mapped[list[SourceUrlDiscovery]] = relationship(
        back_populates="source_url"
    )
