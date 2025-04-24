from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class Streamer(Base):
    __tablename__ = "streamers"

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
    notification_settings = relationship("NotificationSettings", back_populates="streamer")
class Stream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    language = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    twitch_stream_id = Column(String, nullable=True)
    
    @property
    def is_live(self):
        return self.ended_at is None

class StreamEvent(Base):
    __tablename__ = "stream_events"

    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"))
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    language = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    favorite_categories = relationship("FavoriteCategory", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    notify_online = Column(Boolean, default=True)
    notify_offline = Column(Boolean, default=True)
    notify_update = Column(Boolean, default=True)
    notify_favorite_category = Column(Boolean, default=True)
    streamer = relationship("Streamer", back_populates="notification_settings")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    twitch_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    box_art_url = Column(String, nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    favorites = relationship("FavoriteCategory", back_populates="category", cascade="all, delete-orphan")

class FavoriteCategory(Base):
    __tablename__ = "favorite_categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="favorite_categories")
    category = relationship("Category", back_populates="favorites")
    __table_args__ = (UniqueConstraint('user_id', 'category_id', name='uq_user_category'),)

    
class GlobalSettings(Base):
    __tablename__ = "global_settings"
    
    id: int = Column(Integer, primary_key=True)
    notification_url: Optional[str] = Column(String)
    notifications_enabled: bool = Column(Boolean, default=True)
    notify_online_global: bool = Column(Boolean, default=True)
    notify_offline_global: bool = Column(Boolean, default=True)
    notify_update_global: bool = Column(Boolean, default=True)

class RecordingSettings(Base):
    __tablename__ = "recording_settings"
    
    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False)
    output_directory = Column(String, default="/recordings")
    filename_template = Column(String, default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}")
    default_quality = Column(String, default="best")
    use_chapters = Column(Boolean, default=True)
    filename_preset = Column(String, default="default")
    use_category_as_chapter_title = Column(Boolean, default=False)   
      
class StreamerRecordingSettings(Base):
    __tablename__ = "streamer_recording_settings"
    
    id = Column(Integer, primary_key=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    enabled = Column(Boolean, default=True)
    quality = Column(String, default="best")
    custom_filename = Column(String, nullable=True)
    
    streamer = relationship("Streamer", back_populates="recording_settings")

Streamer.recording_settings = relationship("StreamerRecordingSettings", back_populates="streamer", uselist=False, cascade="all, delete-orphan")

class StreamMetadata(Base):
    __tablename__ = "stream_metadata"
    
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
    stream = relationship("Stream", back_populates="metadata")

# Füge die Rückbeziehung zum Stream-Modell hinzu
Stream.metadata = relationship("StreamMetadata", back_populates="stream", uselist=False, cascade="all, delete-orphan")