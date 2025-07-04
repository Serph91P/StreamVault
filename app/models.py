from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from typing import List, Optional, TYPE_CHECKING

# Import type annotation helpers
if TYPE_CHECKING:
    # These imports are only used for type checking
    from app.utils.model_types import (
        NotificationSettings, Stream, StreamMetadata, FavoriteCategory, 
        Streamer, User, Category, StreamEvent
    )

class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    twitch_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False)
    is_live = Column(Boolean, default=False)
    title = Column(String)
    category_name = Column(String)
    language = Column(String)
    last_updated = Column(DateTime(timezone=True))
    profile_image_url = Column(String)
    original_profile_image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notification_settings: List["NotificationSettings"] = relationship("NotificationSettings", back_populates="streamer")
class Stream(Base):
    __tablename__ = "streams"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    language = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    twitch_stream_id = Column(String, nullable=True)
    recording_path = Column(String, nullable=True)  # Path to the recorded MP4 file
    
    # Relationships
    stream_metadata: Optional["StreamMetadata"] = relationship("StreamMetadata", back_populates="stream", uselist=False)
    
    @property
    def is_live(self):
        return self.ended_at is None

class StreamEvent(Base):
    __tablename__ = "stream_events"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"))
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    language = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    favorite_categories: List["FavoriteCategory"] = relationship("FavoriteCategory", back_populates="user", cascade="all, delete-orphan")

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
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    notify_online = Column(Boolean, default=True)
    notify_offline = Column(Boolean, default=True)
    notify_update = Column(Boolean, default=True)
    notify_favorite_category = Column(Boolean, default=True)
    streamer: "Streamer" = relationship("Streamer", back_populates="notification_settings")

class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    twitch_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    box_art_url = Column(String, nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    favorites: List["FavoriteCategory"] = relationship("FavoriteCategory", back_populates="category", cascade="all, delete-orphan")

class FavoriteCategory(Base):
    __tablename__ = "favorite_categories"
    __table_args__ = (UniqueConstraint('user_id', 'category_id', name='uq_user_category'), {'extend_existing': True})
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user: "User" = relationship("User", back_populates="favorite_categories")
    category: "Category" = relationship("Category", back_populates="favorites")

    
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
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    enabled = Column(Boolean, default=True)
    quality = Column(String, default="best")
    custom_filename = Column(String, nullable=True)
    max_streams = Column(Integer, nullable=True)  # Per-streamer override for max recordings
    cleanup_policy = Column(String, nullable=True)  # JSON string for cleanup policy
    
    streamer: "Streamer" = relationship("Streamer", back_populates="recording_settings")

Streamer.recording_settings = relationship("StreamerRecordingSettings", back_populates="streamer", uselist=False, cascade="all, delete-orphan")

class StreamMetadata(Base):
    __tablename__ = "stream_metadata"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"))
    
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
    stream: "Stream" = relationship("Stream", back_populates="stream_metadata")

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