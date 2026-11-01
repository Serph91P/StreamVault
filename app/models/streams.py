"""Streamer, stream history and media metadata mappings."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import warnings
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, column_property
from sqlalchemy.sql import func
from app.database import Base
from app.models.recordings import Recording

if TYPE_CHECKING:
    from app.models.notifications import NotificationSettings
    from app.models.recordings import ActiveRecordingState, StreamerRecordingSettings


class Stream(Base):
    __tablename__ = "streams"
    __table_args__ = (
        Index("idx_streams_streamer_active", "streamer_id", "ended_at"),
        Index("idx_streams_streamer_recent", "streamer_id", "started_at"),
        Index("idx_streams_category_recent", "category_name", "started_at"),
        Index("idx_streams_time_range", "started_at", "ended_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("streamers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    twitch_stream_id: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True, index=True
    )
    recording_path: Mapped[str | None] = mapped_column(String, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    streamer: Mapped[Streamer] = relationship("Streamer", back_populates="streams")
    stream_metadata: Mapped[StreamMetadata | None] = relationship(
        "StreamMetadata", back_populates="stream", uselist=False
    )
    active_recording_state: Mapped[ActiveRecordingState | None] = relationship(
        "ActiveRecordingState",
        back_populates="stream",
        uselist=False,
        cascade="all, delete-orphan",
    )
    recordings: Mapped[list[Recording]] = relationship(
        "Recording", back_populates="stream"
    )
    stream_events: Mapped[list[StreamEvent]] = relationship(
        "StreamEvent", back_populates="stream"
    )

    @property
    def is_live(self):
        return self.ended_at is None


class StreamEvent(Base):
    __tablename__ = "stream_events"
    __table_args__ = (
        Index("idx_stream_events_stream_type", "stream_id", "event_type"),
        Index("idx_stream_events_stream_time", "stream_id", "timestamp"),
        Index("idx_stream_events_type_time", "event_type", "timestamp"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stream_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("streams.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    stream: Mapped[Stream | None] = relationship(
        "Stream", back_populates="stream_events"
    )


class StreamMetadata(Base):
    __tablename__ = "stream_metadata"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stream_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("streams.id", ondelete="CASCADE"), index=True
    )
    thumbnail_path: Mapped[str | None] = mapped_column(String)
    thumbnail_url: Mapped[str | None] = mapped_column(String)
    nfo_path: Mapped[str | None] = mapped_column(String)
    json_path: Mapped[str | None] = mapped_column(String)
    tvshow_nfo_path: Mapped[str | None] = mapped_column(String)
    season_nfo_path: Mapped[str | None] = mapped_column(String)
    chapters_vtt_path: Mapped[str | None] = mapped_column(String)
    chapters_srt_path: Mapped[str | None] = mapped_column(String)
    chapters_ffmpeg_path: Mapped[str | None] = mapped_column(String)
    chapters_xml_path: Mapped[str | None] = mapped_column(String)
    segments_dir_path: Mapped[str | None] = mapped_column(String)
    segments_removed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    avg_viewers: Mapped[int | None] = mapped_column(Integer)
    max_viewers: Mapped[int | None] = mapped_column(Integer)
    follower_count: Mapped[int | None] = mapped_column(Integer)
    stream: Mapped[Stream | None] = relationship(
        "Stream", back_populates="stream_metadata"
    )


class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    twitch_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_live: Mapped[bool | None] = mapped_column(Boolean, default=False, index=True)
    title: Mapped[str | None] = mapped_column(String)
    category_name: Mapped[str | None] = mapped_column(String, index=True)
    language: Mapped[str | None] = mapped_column(String)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_image_url: Mapped[str | None] = mapped_column(String)
    original_profile_image_url: Mapped[str | None] = mapped_column(String)
    offline_image_url: Mapped[str | None] = mapped_column(String)
    original_offline_image_url: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool | None] = mapped_column(Boolean, default=False, index=True)
    auto_record: Mapped[bool | None] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_test_data: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    last_stream_title: Mapped[str | None] = mapped_column(String, nullable=True)
    last_stream_category_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_stream_viewer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_stream_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Eager read expression, not a physical column or per-instance session query.
    _is_recording_snapshot: Mapped[bool] = column_property(
        select(Recording.__table__.c.id)
        .select_from(
            Recording.__table__.join(
                Stream.__table__,
                Recording.__table__.c.stream_id == Stream.__table__.c.id,
            )
        )
        .where(
            Stream.__table__.c.streamer_id == id,
            Recording.__table__.c.status == "recording",
        )
        .correlate_except(Recording.__table__, Stream.__table__)
        .exists()
    )
    notification_settings: Mapped[list[NotificationSettings]] = relationship(
        "NotificationSettings", back_populates="streamer"
    )
    recording_settings: Mapped[StreamerRecordingSettings | None] = relationship(
        "StreamerRecordingSettings",
        back_populates="streamer",
        uselist=False,
        cascade="all, delete-orphan",
    )
    streams: Mapped[list[Stream]] = relationship("Stream", back_populates="streamer")

    @property
    def display_name(self):
        """Deprecated alias for username."""
        warnings.warn(
            "The `display_name` property is deprecated and will be removed in the future. Use `username` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.username

    @property
    def is_recording(self) -> bool:
        """Loaded recording snapshot; refresh/requery explicitly for later state."""
        return bool(self._is_recording_snapshot)

    @property
    def recording_enabled(self) -> bool | None:
        """Compatibility alias for automatic recording."""
        return self.auto_record
