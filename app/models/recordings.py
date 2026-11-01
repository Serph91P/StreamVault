"""Recording configuration and durable capture/processing state mappings."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import json
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base

if TYPE_CHECKING:
    from app.models.streams import Stream, Streamer


class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        Index("idx_recordings_stream_status", "stream_id", "status"),
        Index("idx_recordings_status_time", "status", "start_time"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stream: Mapped[Stream] = relationship("Stream", back_populates="recordings")


class RecordingSettings(Base):
    __tablename__ = "recording_settings"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool | None] = mapped_column(Boolean, default=False)
    output_directory: Mapped[str | None] = mapped_column(String, default="/recordings")
    filename_template: Mapped[str | None] = mapped_column(
        String,
        default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    )
    default_quality: Mapped[str | None] = mapped_column(String, default="best")
    use_chapters: Mapped[bool | None] = mapped_column(Boolean, default=True)
    filename_preset: Mapped[str | None] = mapped_column(String, default="default")
    use_category_as_chapter_title: Mapped[bool | None] = mapped_column(
        Boolean, default=False
    )
    max_streams_per_streamer: Mapped[int | None] = mapped_column(Integer, default=0)
    cleanup_policy: Mapped[str | None] = mapped_column(String, nullable=True)
    enable_proxy: Mapped[bool | None] = mapped_column(Boolean, default=True)
    proxy_health_check_enabled: Mapped[bool | None] = mapped_column(
        Boolean, default=True
    )
    proxy_health_check_interval_seconds: Mapped[int | None] = mapped_column(
        Integer, default=300
    )
    proxy_max_consecutive_failures: Mapped[int | None] = mapped_column(
        Integer, default=3
    )
    fallback_to_direct_connection: Mapped[bool | None] = mapped_column(
        Boolean, default=True
    )


class StreamerRecordingSettings(Base):
    __tablename__ = "streamer_recording_settings"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    streamer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streamers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool | None] = mapped_column(Boolean, default=True)
    quality: Mapped[str | None] = mapped_column(String, default="best")
    custom_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    max_streams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cleanup_policy: Mapped[str | None] = mapped_column(String, nullable=True)
    use_global_cleanup_policy: Mapped[bool | None] = mapped_column(
        Boolean, default=True
    )
    supported_codecs: Mapped[str | None] = mapped_column(String, nullable=True)
    # Retained legacy storage only; this refactor does not reactivate priority.
    twitch_auth_priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    streamer: Mapped[Streamer] = relationship(
        "Streamer", back_populates="recording_settings"
    )


class ActiveRecordingState(Base):
    """Durable process ownership and recovery metadata."""

    __tablename__ = "active_recordings_state"
    __table_args__ = (
        Index("ix_active_recordings_stream_id", "stream_id"),
        Index("ix_active_recordings_status", "status"),
        Index("ix_active_recordings_heartbeat", "last_heartbeat"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    recording_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recordings.id"), nullable=False
    )
    process_id: Mapped[int] = mapped_column(Integer, nullable=False)
    process_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    streamer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ts_output_path: Mapped[str] = mapped_column(String(500), nullable=False)
    force_mode: Mapped[bool | None] = mapped_column(Boolean, default=False)
    quality: Mapped[str | None] = mapped_column(String(50), default="best")
    status: Mapped[str | None] = mapped_column(String(50), default="active")
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    stream: Mapped[Stream] = relationship(
        "Stream", back_populates="active_recording_state"
    )
    recording: Mapped[Recording] = relationship("Recording")

    def get_config(self):
        if self.config_json:
            return json.loads(self.config_json)
        return {}

    def set_config(self, config_dict):
        self.config_json = json.dumps(config_dict) if config_dict else None

    def is_stale(self, max_age_seconds=300):
        if not self.last_heartbeat:
            return True
        age = (
            datetime.now(self.last_heartbeat.tzinfo) - self.last_heartbeat
        ).total_seconds()
        return age > max_age_seconds


class RecordingProcessingState(Base):
    """Durable per-recording step outcomes for idempotent processing."""

    __tablename__ = "recording_processing_state"
    __table_args__ = (
        Index("ix_rps_recording_id", "recording_id", unique=True),
        Index("ix_rps_stream_id", "stream_id"),
        Index("ix_rps_updated_at", "updated_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    stream_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    streamer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streamers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metadata_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    chapters_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    mp4_remux_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    mp4_validation_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    thumbnail_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    cleanup_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def set_task_ids(self, task_ids: dict):
        self.task_ids_json = json.dumps(task_ids) if task_ids else None

    def get_task_ids(self):
        try:
            return json.loads(self.task_ids_json) if self.task_ids_json else {}
        except Exception:
            return {}
