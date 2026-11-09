"""One filesystem metadata snapshot per stream, separate from recording truth."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from app.database import Base


class VideoCatalogEntry(Base):
    __tablename__ = "video_catalog_entries"

    stream_id = Column(
        Integer, ForeignKey("streams.id", ondelete="CASCADE"), primary_key=True
    )
    file_path = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=False, default=0)
    duration = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    recording_id = Column(Integer, nullable=True)
    is_recording = Column(Boolean, nullable=False, default=False)
    has_thumbnail = Column(Boolean, nullable=False, default=False)
    state = Column(String(16), nullable=False, default="pending", index=True)
    checked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error_type = Column(String(64), nullable=True)
    dirty = Column(Boolean, nullable=False, default=False, index=True)
    revision = Column(Integer, nullable=False, default=0)
    __mapper_args__ = {"version_id_col": revision, "version_id_generator": False}
