"""Worker-owned catalog transactions for EventSub handlers."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Recording, Stream, Streamer


@dataclass(frozen=True)
class OfflineEvent:
    streamer_id: int
    username: str
    stream_id: int | None
    profile_image_url: str | None


def prepare_offline(
    session_factory: Callable[[], Session], broadcaster_id: str
) -> OfflineEvent | None:
    with session_factory() as session:
        streamer = (
            session.query(Streamer).filter(Streamer.twitch_id == broadcaster_id).first()
        )
        if streamer is None:
            return None
        streamer.is_live = False
        streamer.last_updated = datetime.now(timezone.utc)
        streams = (
            session.query(Stream)
            .filter(Stream.streamer_id == streamer.id, Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .all()
        )
        current = streams[0] if streams else None
        ended_at = datetime.now(timezone.utc)
        # Older captures remain recovery-owned, but cannot attract new chapter events.
        for stream in streams:
            stream.ended_at = ended_at
        if current:
            streamer.last_stream_title = current.title
            streamer.last_stream_category_name = current.category_name
            streamer.last_stream_ended_at = current.ended_at
        session.commit()
        return OfflineEvent(
            streamer_id=streamer.id,
            username=streamer.username,
            stream_id=current.id if current else None,
            profile_image_url=streamer.profile_image_url,
        )


def offline_recording_id(
    session_factory: Callable[[], Session], event: OfflineEvent
) -> int | None:
    with session_factory() as session:
        stream_id = event.stream_id
        if stream_id is None:
            recent = (
                session.query(Stream)
                .filter(Stream.streamer_id == event.streamer_id)
                .order_by(Stream.created_at.desc())
                .first()
            )
            if recent is None:
                return None
            stream_id = recent.id
        recording = (
            session.query(Recording)
            .filter(Recording.stream_id == stream_id, Recording.status == "recording")
            .first()
        )
        return recording.id if recording else None
