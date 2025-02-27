from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
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

    streamer = relationship("Streamer", back_populates="notification_settings")
    
class GlobalSettings(Base):
    __tablename__ = "global_settings"
    
    id: int = Column(Integer, primary_key=True)
    notification_url: Optional[str] = Column(String)
    notifications_enabled: bool = Column(Boolean, default=True)
    notify_online_global: bool = Column(Boolean, default=True)
    notify_offline_global: bool = Column(Boolean, default=True)
    notify_update_global: bool = Column(Boolean, default=True)