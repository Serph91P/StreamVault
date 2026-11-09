"""Encrypted proxy configuration and health statistics mappings."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, inspect
from sqlalchemy.orm import Mapped, mapped_column, object_session
from sqlalchemy.sql import func
from app.database import Base


class ProxySettings(Base):
    """Encrypted credentials; diagnostic projections remain host/port-only."""

    __tablename__ = "proxy_settings"
    __table_args__ = (
        Index("ix_proxy_enabled", "enabled"),
        Index("ix_proxy_health_status", "health_status"),
        Index("ix_proxy_priority", "priority"),
        Index(
            "ix_proxy_enabled_health_priority", "enabled", "health_status", "priority"
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    _proxy_url_encrypted: Mapped[str] = mapped_column(
        "proxy_url", String(1000), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    health_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    average_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_recordings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_recordings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def proxy_url(self) -> str:
        from app.utils.proxy_encryption import get_cached_proxy_encryption

        state = inspect(self)
        try:
            session = object_session(self)
            encryption = (
                get_cached_proxy_encryption(session)
                if session is not None
                else get_cached_proxy_encryption()
            )
            ciphertext = state.attrs["_proxy_url_encrypted"].loaded_value
            if not isinstance(ciphertext, str):
                raise RuntimeError("Proxy ciphertext snapshot is not loaded")
            return encryption.decrypt(ciphertext)
        except Exception as e:
            import logging

            logger = logging.getLogger("streamvault")
            logger.error(
                "Failed to decrypt proxy URL for ID %s: %s",
                state.identity[0] if state.identity else None,
                e,
            )
            return ""

    @proxy_url.setter
    def proxy_url(self, plaintext_url: str):
        from app.utils.proxy_encryption import get_cached_proxy_encryption

        if plaintext_url:
            session = object_session(self)
            encryption = (
                get_cached_proxy_encryption(session)
                if session is not None
                else get_cached_proxy_encryption()
            )
            self._proxy_url_encrypted = encryption.encrypt(plaintext_url)
        else:
            self._proxy_url_encrypted = ""

    @property
    def masked_url(self) -> str:
        from app.utils.security import sanitize_proxy_url_for_logging

        return sanitize_proxy_url_for_logging(self.proxy_url)

    def calculate_success_rate(self) -> Optional[float]:
        if self.total_recordings == 0:
            return None
        return (
            (self.total_recordings - self.failed_recordings) / self.total_recordings
        ) * 100.0

    def update_success_rate(self):
        self.success_rate = self.calculate_success_rate()

    def to_dict(self, mask_password: bool = True) -> dict:
        masked_url = self.masked_url
        return {
            "id": self.id,
            "proxy_url": masked_url if mask_password else self.proxy_url,
            "masked_url": masked_url,
            "priority": self.priority,
            "enabled": self.enabled,
            "last_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "health_status": self.health_status,
            "response_time_ms": self.average_response_time_ms,
            "consecutive_failures": self.consecutive_failures,
            "last_error": None,
            "total_requests": self.total_recordings,
            "successful_requests": self.total_recordings - self.failed_recordings,
            "failed_requests": self.failed_recordings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
