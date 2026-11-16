"""Global configuration and durable system flags."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class GlobalSettings(Base):
    __tablename__ = "global_settings"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_url: Mapped[str | None] = mapped_column(String)
    notifications_enabled: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_online_global: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_offline_global: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_update_global: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_favorite_category_global: Mapped[bool | None] = mapped_column(
        Boolean, default=True
    )
    http_proxy: Mapped[str | None] = mapped_column(String)
    https_proxy: Mapped[str | None] = mapped_column(String)
    notify_recording_started: Mapped[bool | None] = mapped_column(
        Boolean, default=False
    )
    notify_recording_failed: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notify_recording_completed: Mapped[bool | None] = mapped_column(
        Boolean, default=False
    )
    supported_codecs: Mapped[str | None] = mapped_column(String, default="h264,h265")
    prefer_higher_quality: Mapped[bool | None] = mapped_column(Boolean, default=True)
    twitch_max_concurrent_upstreams: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    proxy_encryption_key: Mapped[str | None] = mapped_column(String, nullable=True)
    twitch_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    twitch_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    twitch_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)


class SystemState(Base):
    """Singleton durable onboarding state, independent of browser storage."""

    __tablename__ = "system_state"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    welcome_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    welcome_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SystemConfig(Base):
    __tablename__ = "system_config"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
