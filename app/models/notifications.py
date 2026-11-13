"""Notification preferences, read state and Web Push subscriptions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.streams import Streamer


class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    streamer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streamers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notify_online: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_offline: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_update: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_favorite_category: Mapped[bool | None] = mapped_column(Boolean, default=True)
    streamer: Mapped[Streamer] = relationship(
        "Streamer", back_populates="notification_settings"
    )


class NotificationState(Base):
    __tablename__ = "notification_state"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    last_read_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_cleared_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user: Mapped[User] = relationship("User", back_populates="notification_state")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subscription_data: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
