"""Recording persistence: one complete transaction per blocking worker operation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from types import TracebackType
from typing import TypedDict, NotRequired

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Recording, Stream, Streamer, StreamEvent
from app.services.recording.recording_values import (
    RecordingStream,
    RecordingValue,
    StreamerIdentity,
)
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.retry_decorator import database_retry, RetryableError, NonRetryableError


class NewStream(TypedDict):
    streamer_id: int
    title: NotRequired[str | None]
    category_name: NotRequired[str | None]
    language: NotRequired[str | None]
    started_at: NotRequired[datetime | None]
    twitch_stream_id: NotRequired[str | None]
    external_id: NotRequired[str | None]


class RecordingDatabaseService:
    """No retained Session; reads return immutable runtime values, not ORM rows."""

    def __init__(
        self, db: None = None, *, session_factory: Callable[[], Session] | None = None
    ):
        if db is not None:
            raise TypeError("Pass session_factory, not a live Session")
        self._session_factory = session_factory
        # Legacy facade introspection; there is deliberately no long-lived Session.
        self.db = None

    @database_retry
    async def _run[T](self, operation: Callable[[Session], T]) -> T:
        def work() -> T:
            try:
                with (self._session_factory or SessionLocal)() as session:
                    with session.begin():
                        return operation(session)
            except NonRetryableError:
                raise
            except IntegrityError as error:
                raise NonRetryableError(
                    "Recording database constraint violation"
                ) from error
            except SQLAlchemyError as error:
                raise RetryableError("Recording database operation failed") from error

        return await run_in_thread_pool(work)

    @staticmethod
    def _required_recording(session: Session, recording_id: int) -> Recording:
        row = session.get(Recording, recording_id)
        if row is None:
            raise NonRetryableError(f"Recording {recording_id} not found")
        return row

    async def update_recording_status(
        self,
        recording_id: int,
        status: str,
        path: str | None = None,
        duration_seconds: int | None = None,
    ) -> None:
        def work(session: Session) -> None:
            row = self._required_recording(session, recording_id)
            row.status = status
            if path:
                row.path = path
            if duration_seconds is not None:
                row.duration = duration_seconds
            if status in ("completed", "failed"):
                row.end_time = datetime.utcnow()

        await self._run(work)

    async def create_recording(self, stream_id: int, file_path: str) -> RecordingValue:
        def work(session: Session) -> RecordingValue:
            row = Recording(
                stream_id=stream_id,
                path=file_path,
                status="recording",
                start_time=datetime.utcnow(),
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return RecordingValue.from_model(row)

        return await self._run(work)

    async def get_recording(self, recording_id: int) -> RecordingValue | None:
        def work(session: Session) -> RecordingValue | None:
            row = session.scalar(
                select(Recording)
                .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                .where(Recording.id == recording_id)
            )
            return RecordingValue.from_model(row) if row is not None else None

        return await self._run(work)

    async def get_recording_by_id(self, recording_id: int) -> RecordingValue | None:
        return await self.get_recording(recording_id)

    async def get_active_recordings_from_db(self) -> list[RecordingValue]:
        def work(session: Session) -> list[RecordingValue]:
            rows = session.scalars(
                select(Recording)
                .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                .where(Recording.status.in_(["recording", "processing"]))
            )
            return [RecordingValue.from_model(row) for row in rows]

        return await self._run(work)

    async def ensure_stream_ended(self, stream_id: int) -> None:
        def work(session: Session) -> None:
            row = session.get(Stream, stream_id)
            if row is not None and not row.ended_at:
                row.ended_at = datetime.utcnow()

        await self._run(work)

    async def get_stream_with_streamer(
        self, stream_id: int
    ) -> tuple[RecordingStream, StreamerIdentity] | None:
        stream = await self.get_stream_by_id(stream_id)
        return (
            (stream, stream.streamer)
            if stream is not None and stream.streamer is not None
            else None
        )

    async def get_recordings_by_status(self, status: str) -> list[RecordingValue]:
        def work(session: Session) -> list[RecordingValue]:
            rows = session.scalars(
                select(Recording)
                .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                .where(Recording.status == status)
            )
            return [RecordingValue.from_model(row) for row in rows]

        return await self._run(work)

    async def update_recording_path(self, recording_id: int, new_path: str) -> None:
        def work(session: Session) -> None:
            self._required_recording(session, recording_id).path = new_path

        await self._run(work)

    async def mark_active_stream_recording_failed(
        self, stream_id: int, error_message: str, failure_reason: str
    ) -> int | None:
        def work(session: Session) -> int | None:
            row = session.scalar(
                select(Recording).where(
                    Recording.stream_id == stream_id, Recording.status == "recording"
                )
            )
            if row is None:
                return None
            row.status = "failed"
            row.error_message = error_message
            row.failure_reason = failure_reason
            row.failure_timestamp = datetime.now(timezone.utc)
            row.end_time = datetime.now(timezone.utc)
            return row.id

        return await self._run(work)

    async def mark_recording_failed(
        self, recording_id: int, error_message: str | None = None
    ) -> None:
        def work(session: Session) -> None:
            row = self._required_recording(session, recording_id)
            row.status = "failed"
            row.end_time = datetime.utcnow()
            if error_message:
                row.error_message = error_message

        await self._run(work)

    async def get_streamer_by_id(self, streamer_id: int) -> StreamerIdentity | None:
        def work(session: Session) -> StreamerIdentity | None:
            row = session.get(Streamer, streamer_id)
            return StreamerIdentity.from_model(row) if row is not None else None

        return await self._run(work)

    async def get_stream_by_id(self, stream_id: int) -> RecordingStream | None:
        def work(session: Session) -> RecordingStream | None:
            row = session.scalar(
                select(Stream)
                .options(joinedload(Stream.streamer))
                .where(Stream.id == stream_id)
            )
            return RecordingStream.from_model(row) if row is not None else None

        return await self._run(work)

    async def get_stream_by_twitch_stream_id(
        self, twitch_stream_id: str
    ) -> RecordingStream | None:
        def work(session: Session) -> RecordingStream | None:
            row = session.scalar(
                select(Stream)
                .options(joinedload(Stream.streamer))
                .where(Stream.twitch_stream_id == twitch_stream_id)
            )
            return RecordingStream.from_model(row) if row is not None else None

        return await self._run(work)

    async def create_stream(self, stream_data: NewStream) -> RecordingStream:
        def work(session: Session) -> RecordingStream:
            row = Stream(
                streamer_id=stream_data["streamer_id"],
                title=stream_data.get("title", "Unknown Stream"),
                category_name=stream_data.get("category_name", "Unknown"),
                language=stream_data.get("language", "en"),
                started_at=stream_data.get("started_at", datetime.now()),
                twitch_stream_id=stream_data.get(
                    "twitch_stream_id", stream_data.get("external_id", "unknown")
                ),
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return RecordingStream.from_model(row)

        return await self._run(work)

    async def ensure_initial_stream_events(
        self,
        stream_id: int,
        *,
        title: str | None = None,
        category_name: str | None = None,
        language: str | None = "en",
    ) -> None:
        def work(session: Session) -> None:
            # Same guarded-transaction pattern as upstream leases; SQLite has no row locks.
            if session.get_bind().dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            stream = session.scalar(
                select(Stream).where(Stream.id == stream_id).with_for_update()
            )
            if stream is None:
                return
            existing = session.scalar(
                select(StreamEvent.id)
                .where(
                    StreamEvent.stream_id == stream_id,
                    StreamEvent.event_type == "stream.online",
                )
                .limit(1)
            )
            if existing is not None:
                return
            started_at = stream.started_at or datetime.now(timezone.utc)
            values = {
                "stream_id": stream_id,
                "title": stream.title or title,
                "category_name": stream.category_name or category_name,
                "language": stream.language or language,
            }
            session.add(
                StreamEvent(**values, event_type="stream.online", timestamp=started_at)
            )
            if values["category_name"]:
                session.add(
                    StreamEvent(
                        **values,
                        event_type="channel.update",
                        timestamp=started_at - timedelta(seconds=1),
                    )
                )

        await self._run(work)

    def close_session(self) -> None:
        """Compatibility hook: every operation already closed its own scope."""

    def __enter__(self) -> RecordingDatabaseService:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close_session()
