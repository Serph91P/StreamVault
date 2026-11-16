"""Durable job identities; the in-memory queue is only an execution window."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BackgroundTask(Base):
    __tablename__ = "background_tasks"
    __table_args__ = (
        Index(
            "ix_background_tasks_dispatch",
            "status",
            "ready_at",
            "priority",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    streamer_key: Mapped[str] = mapped_column(String(256), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ready_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    owner_token: Mapped[str | None] = mapped_column(String(36))
    owner_pid: Mapped[int | None] = mapped_column(Integer)
    owner_started: Mapped[float | None] = mapped_column(Float)
    owner_host: Mapped[str | None] = mapped_column(String(256))


class BackgroundTaskDependency(Base):
    __tablename__ = "background_task_dependencies"
    task_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dependency_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
