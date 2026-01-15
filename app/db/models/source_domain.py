from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceDomain(Base):
    __tablename__ = "source_domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
