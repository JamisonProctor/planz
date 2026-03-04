from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    # JSON string e.g. '["theater","museum"]'; None means all categories
    selected_categories: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_free: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="preference")
