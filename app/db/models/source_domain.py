from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.source_url import SourceUrl


class SourceDomain(Base):
    __tablename__ = "source_domains"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
    )

    urls: Mapped[list[SourceUrl]] = relationship(back_populates="domain")


def get_or_create_domain(session: Session, domain: str) -> SourceDomain:
    existing = session.scalar(select(SourceDomain).where(SourceDomain.domain == domain))
    if existing:
        return existing

    domain_row = SourceDomain(domain=domain)
    session.add(domain_row)
    session.flush()
    return domain_row
