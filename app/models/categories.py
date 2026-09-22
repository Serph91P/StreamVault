"""Typed SQLAlchemy models for categories and user favorites.

This is the first low-risk extraction from the legacy model registry. Table and
relationship names intentionally remain unchanged so existing migrations,
queries, and ``app.models`` imports keep their historical contract.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models import User


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    twitch_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    box_art_url: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    favorites: Mapped[list["FavoriteCategory"]] = relationship(
        "FavoriteCategory", back_populates="category", cascade="all, delete-orphan"
    )


class FavoriteCategory(Base):
    __tablename__ = "favorite_categories"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_user_category"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    user: Mapped["User | None"] = relationship(
        "User", back_populates="favorite_categories"
    )
    category: Mapped[Category | None] = relationship(
        "Category", back_populates="favorites"
    )
