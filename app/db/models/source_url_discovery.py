from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SourceUrlDiscovery(Base):
    __tablename__ = "source_url_discoveries"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    search_result_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_results.id")
    )
    source_url_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_urls.id")
    )

    search_result: Mapped["SearchResult"] = relationship(back_populates="discoveries")
    source_url: Mapped["SourceUrl"] = relationship(back_populates="discoveries")
