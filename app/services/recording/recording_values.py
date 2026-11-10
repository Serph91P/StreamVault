"""Recording runtime read values, materialized while their ORM session is owned."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models import Recording, Stream, Streamer


@dataclass(frozen=True)
class StreamerIdentity:
    id: int
    twitch_id: str
    username: str

    @classmethod
    def from_model(cls, row: Streamer) -> StreamerIdentity:
        return cls(id=row.id, twitch_id=row.twitch_id, username=row.username)


@dataclass(frozen=True)
class RecordingStream:
    id: int
    streamer_id: int
    title: str | None
    category_name: str | None
    language: str | None
    started_at: datetime | None
    ended_at: datetime | None
    twitch_stream_id: str | None
    recording_path: str | None
    episode_number: int | None
    created_at: datetime | None
    streamer: StreamerIdentity | None

    @property
    def is_live(self) -> bool:
        return self.ended_at is None

    @classmethod
    def from_model(cls, row: Stream) -> RecordingStream:
        return cls(
            id=row.id,
            streamer_id=row.streamer_id,
            title=row.title,
            category_name=row.category_name,
            language=row.language,
            started_at=row.started_at,
            ended_at=row.ended_at,
            twitch_stream_id=row.twitch_stream_id,
            recording_path=row.recording_path,
            episode_number=row.episode_number,
            created_at=row.created_at,
            streamer=StreamerIdentity.from_model(row.streamer)
            if row.streamer is not None
            else None,
        )


@dataclass(frozen=True)
class RecordingValue:
    id: int
    stream_id: int
    start_time: datetime
    end_time: datetime | None
    status: str
    duration: int | float | None
    path: str | None
    created_at: datetime | None
    error_message: str | None
    failure_reason: str | None
    failure_timestamp: datetime | None
    stream: RecordingStream | None

    @classmethod
    def from_model(cls, row: Recording) -> RecordingValue:
        return cls(
            id=row.id,
            stream_id=row.stream_id,
            start_time=row.start_time,
            end_time=row.end_time,
            status=row.status,
            duration=row.duration,
            path=row.path,
            created_at=row.created_at,
            error_message=row.error_message,
            failure_reason=row.failure_reason,
            failure_timestamp=row.failure_timestamp,
            stream=RecordingStream.from_model(row.stream)
            if row.stream is not None
            else None,
        )
