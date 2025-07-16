from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import json

class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index('idx_recordings_stream_status', 'stream_id', 'status'),  # For finding recordings by stream and status
        Index('idx_recordings_status_time', 'status', 'start_time'),  # For finding recordings by status and time
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, index=True)  # "recording", "completed", "error"
    duration = Column(Integer, nullable=True)  # Duration in seconds
    path = Column(String, nullable=True)  # Path to the recording file
    
    # Relationship to Stream
    stream = relationship("Stream", backref="recordings")

class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    twitch_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    is_live = Column(Boolean, default=False, index=True)
    title = Column(String)
    category_name = Column(String, index=True)
    language = Column(String)
    last_updated = Column(DateTime(timezone=True))
    profile_image_url = Column(String)
    original_profile_image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notification_settings = relationship("NotificationSettings", back_populates="streamer")
class Stream(Base):
    __tablename__ = "streams"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index('idx_streams_streamer_active', 'streamer_id', 'ended_at'),  # For finding active streams
        Index('idx_streams_streamer_recent', 'streamer_id', 'started_at'),  # For recent streams by streamer
        Index('idx_streams_category_recent', 'category_name', 'started_at'),  # For recent streams by category
        Index('idx_streams_time_range', 'started_at', 'ended_at'),  # For time-based queries
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True, index=True)
    twitch_stream_id = Column(String, nullable=True, index=True)
    recording_path = Column(String, nullable=True)  # Path to the recorded MP4 file
    episode_number = Column(Integer, nullable=True)  # Episode number for this stream
    
    # Relationships
    stream_metadata = relationship("StreamMetadata", back_populates="stream", uselist=False)
    active_recording_state = relationship("ActiveRecordingState", back_populates="stream", uselist=False)
    
    @property
    def is_live(self):
        return self.ended_at is None

class StreamEvent(Base):
    __tablename__ = "stream_events"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index('idx_stream_events_stream_type', 'stream_id', 'event_type'),  # For finding events by stream and type
        Index('idx_stream_events_stream_time', 'stream_id', 'timestamp'),  # For chronological events by stream
        Index('idx_stream_events_type_time', 'event_type', 'timestamp'),  # For recent events by type
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), index=True)
    event_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    language = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    favorite_categories = relationship("FavoriteCategory", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)
    notify_online = Column(Boolean, default=True)
    notify_offline = Column(Boolean, default=True)
    notify_update = Column(Boolean, default=True)
    notify_favorite_category = Column(Boolean, default=True)
    streamer = relationship("Streamer", back_populates="notification_settings")

class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    twitch_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    box_art_url = Column(String, nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    favorites = relationship("FavoriteCategory", back_populates="category", cascade="all, delete-orphan")

class FavoriteCategory(Base):
    __tablename__ = "favorite_categories"
    __table_args__ = (UniqueConstraint('user_id', 'category_id', name='uq_user_category'), {'extend_existing': True})
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="favorite_categories")
    category = relationship("Category", back_populates="favorites")

    
class GlobalSettings(Base):
    __tablename__ = "global_settings"
    __table_args__ = {'extend_existing': True}
    
    id: int = Column(Integer, primary_key=True)
    notification_url: Optional[str] = Column(String)
    notifications_enabled: bool = Column(Boolean, default=True)
    notify_online_global: bool = Column(Boolean, default=True)
    notify_offline_global: bool = Column(Boolean, default=True)
    notify_update_global: bool = Column(Boolean, default=True)
    notify_favorite_category_global: bool = Column(Boolean, default=True)
    http_proxy: Optional[str] = Column(String)
    https_proxy: Optional[str] = Column(String)

class RecordingSettings(Base):
    __tablename__ = "recording_settings"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False)
    output_directory = Column(String, default="/recordings")
    filename_template = Column(String, default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}")
    default_quality = Column(String, default="best")
    use_chapters = Column(Boolean, default=True)
    filename_preset = Column(String, default="default")
    use_category_as_chapter_title = Column(Boolean, default=False)
    max_streams_per_streamer = Column(Integer, default=0)  # 0 = unlimited
    cleanup_policy = Column(String, nullable=True)  # JSON string for cleanup policy
      
class StreamerRecordingSettings(Base):
    __tablename__ = "streamer_recording_settings"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, default=True)
    quality = Column(String, default="best")
    custom_filename = Column(String, nullable=True)
    max_streams = Column(Integer, nullable=True)  # Per-streamer override for max recordings
    cleanup_policy = Column(String, nullable=True)  # JSON string for cleanup policy
    
    streamer = relationship("Streamer", back_populates="recording_settings")

Streamer.recording_settings = relationship("StreamerRecordingSettings", back_populates="streamer", uselist=False, cascade="all, delete-orphan")

class StreamMetadata(Base):
    __tablename__ = "stream_metadata"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), index=True)
    
    # Thumbnails
    thumbnail_path = Column(String)
    thumbnail_url = Column(String)
    
    # Metadata files
    nfo_path = Column(String)
    json_path = Column(String)
    
    # Chat logs
    chat_path = Column(String)
    chat_srt_path = Column(String)
    
    # Kapitelmarker
    chapters_path = Column(String)
    chapters_vtt_path = Column(String)
    chapters_srt_path = Column(String)
    chapters_ffmpeg_path = Column(String)
    
    # Stream info stats
    avg_viewers = Column(Integer)
    max_viewers = Column(Integer)
    follower_count = Column(Integer)
    
    # Beziehung zum Stream
    stream = relationship("Stream", back_populates="stream_metadata")

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String, unique=True, nullable=False)
    subscription_data = Column(Text, nullable=False)  # JSON string of the subscription object
    user_agent = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class SystemConfig(Base):
    __tablename__ = "system_config"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ActiveRecordingState(Base):
    """
    Persistent state for active recordings
    
    This table tracks active recording processes and survives application restarts.
    It enables recovery of running recordings after crashes or deployments.
    """
    __tablename__ = "active_recordings_state"
    __table_args__ = (
        Index('ix_active_recordings_stream_id', 'stream_id'),
        Index('ix_active_recordings_status', 'status'),
        Index('ix_active_recordings_heartbeat', 'last_heartbeat'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey('streams.id'), nullable=False, unique=True)
    recording_id = Column(Integer, ForeignKey('recordings.id'), nullable=False)
    process_id = Column(Integer, nullable=False)  # OS process ID
    process_identifier = Column(String(100), nullable=False)  # Internal process identifier
    streamer_name = Column(String(100), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ts_output_path = Column(String(500), nullable=False)
    force_mode = Column(Boolean, default=False)
    quality = Column(String(50), default='best')
    status = Column(String(50), default='active')  # active, stopping, error
    last_heartbeat = Column(DateTime(timezone=True), nullable=False)
    config_json = Column(Text, nullable=True)  # Serialized config
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    stream = relationship("Stream", back_populates="active_recording_state")
    recording = relationship("Recording")
    
    def get_config(self):
        """Get deserialized config"""
        if self.config_json:
            return json.loads(self.config_json)
        return {}
    
    def set_config(self, config_dict):
        """Set serialized config"""
        self.config_json = json.dumps(config_dict) if config_dict else None
    
    def is_stale(self, max_age_seconds=300):
        """Check if heartbeat is stale (default 5 minutes)"""
        if not self.last_heartbeat:
            return True
        age = (datetime.now(self.last_heartbeat.tzinfo) - self.last_heartbeat).total_seconds()
        return age > max_age_seconds
