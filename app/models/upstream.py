"""Durable upstream leases and singleton fencing state; storage ABI unchanged."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class TwitchUpstreamCoordinationState(Base):
    __tablename__ = "twitch_upstream_coordination_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_twitch_upstream_coordination_singleton"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TwitchUpstreamLease(Base):
    __tablename__ = "twitch_upstream_leases"
    __table_args__ = (
        Index("ix_twitch_upstream_leases_state_expiry", "state", "expires_at"),
        Index("ix_twitch_upstream_leases_auth_state", "auth_key", "state"),
        Index("ix_twitch_upstream_leases_owner_state", "owner_user_id", "state"),
        Index("ix_twitch_upstream_leases_recording_id", "recording_id"),
        Index("uq_twitch_upstream_leases_channel_key", "channel_key", unique=True),
        CheckConstraint(
            "purpose IN ('RECORDING', 'LIVE', 'ROTATION', 'RECOVERY')",
            name="ck_twitch_upstream_leases_purpose",
        ),
        CheckConstraint(
            "state IN ('STARTING', 'ACTIVE', 'ROTATING', 'RECOVERING', 'RELEASED')",
            name="ck_twitch_upstream_leases_state",
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_key: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    recording_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True
    )
    live_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    process_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    process_start_fingerprint: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Legacy persisted handoff fields remain inert; no priority reactivation.
    auth_priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    anonymous_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    auth_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    handoff_target_channel: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    handoff_action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    handoff_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    handoff_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    partial_recording_warning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
