"""Durable job identities; the in-memory queue is only an execution window."""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

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

    id = Column(String(128), primary_key=True)
    task_type = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=False)
    streamer_key = Column(String(256), nullable=False)
    priority = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    ready_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False)
    error_message = Column(Text)
    owner_token = Column(String(36))
    owner_pid = Column(Integer)
    owner_started = Column(Float)
    owner_host = Column(String(256))


class BackgroundTaskDependency(Base):
    __tablename__ = "background_task_dependencies"
    task_id = Column(
        String(128),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dependency_id = Column(
        String(128),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
