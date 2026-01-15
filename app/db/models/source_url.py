from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceUrl(Base):
    __tablename__ = "source_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    domain_id: Mapped[int | None] = mapped_column(ForeignKey("source_domains.id"), nullable=True)
