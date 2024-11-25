from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Streamer(Base):
    __tablename__ = "streamers"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)

class Stream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id"), nullable=False)
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
