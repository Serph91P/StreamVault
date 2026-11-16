"""One filesystem metadata snapshot per stream, separate from recording truth."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class VideoCatalogEntry(Base):
    __tablename__ = "video_catalog_entries"

    stream_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("streams.id", ondelete="CASCADE"), primary_key=True
    )
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recording_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_recording: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_thumbnail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dirty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    __mapper_args__ = {"version_id_col": revision, "version_id_generator": False}
