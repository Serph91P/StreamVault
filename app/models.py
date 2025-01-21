from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime

class Streamer(Base):
    __tablename__ = "streamers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    twitch_id = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Stream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    category = Column(String, nullable=True)
    language = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class StreamEvent(Base):
    __tablename__ = "stream_events"
    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"))
    event_type = Column(String)
    title = Column(String, nullable=True)
    category = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

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