"""Worker-owned catalog transactions for EventSub handlers."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Category,
    FavoriteCategory,
    NotificationSettings,
    Recording,
    Stream,
    Streamer,
    StreamEvent,
    User,
)


@dataclass(frozen=True)
class UpdateEvent:
    streamer_id: int
    username: str
    profile_image_url: str | None
    is_live: bool | None


def update_broadcaster_exists(
    session_factory: Callable[[], Session], broadcaster_id: str
) -> bool:
    with session_factory() as session:
        return (
            session.query(Streamer.id)
            .filter(Streamer.twitch_id == broadcaster_id)
            .first()
            is not None
        )


def prepare_update(
    session_factory: Callable[[], Session],
    data: Mapping[str, str],
    category_name: str | None,
    resolve_target: Callable[[Session, int], Stream | None],
) -> UpdateEvent | None:
    with session_factory() as session:
        streamer = (
            session.query(Streamer)
            .filter(Streamer.twitch_id == data["broadcaster_user_id"])
            .first()
        )
        if streamer is None:
            return None
        streamer.title = data.get("title")
        streamer.category_name = category_name
        streamer.language = data.get("language")
        streamer.last_updated = datetime.now(timezone.utc)
        session.commit()
        stream = resolve_target(session, streamer.id)
        if stream is not None:
            if data.get("title"):
                stream.title = data["title"]
            if category_name:
                stream.category_name = category_name
            if data.get("language"):
                stream.language = data["language"]
            session.add(
                StreamEvent(
                    stream_id=stream.id,
                    event_type="channel.update",
                    title=data.get("title"),
                    category_name=category_name,
                    language=data.get("language"),
                    timestamp=datetime.now(timezone.utc),
                )
            )
            session.commit()
        return UpdateEvent(
            streamer.id, streamer.username, streamer.profile_image_url, streamer.is_live
        )


def update_category_exists(
    session_factory: Callable[[], Session], category_id: str
) -> bool:
    with session_factory() as session:
        return (
            session.query(Category.id).filter(Category.twitch_id == category_id).first()
            is not None
        )


def prepare_update_category(
    session_factory: Callable[[], Session],
    category_id: str,
    category_name: str,
    box_art_url: str | None,
    streamer_id: int,
) -> tuple[int, int]:
    with session_factory() as session:
        category = (
            session.query(Category).filter(Category.twitch_id == category_id).first()
        )
        if category is None:
            category = Category(
                twitch_id=category_id, name=category_name, box_art_url=box_art_url
            )
            session.add(category)
        else:
            category.name = category_name
            category.last_seen = datetime.now(timezone.utc)
        session.commit()
        subscribers = (
            session.query(User.id)
            .join(FavoriteCategory)
            .filter(FavoriteCategory.category_id == category.id)
            .all()
        )
        settings = (
            session.query(NotificationSettings)
            .filter(NotificationSettings.streamer_id == streamer_id)
            .first()
            if subscribers
            else None
        )
        return category.id, len(
            subscribers
        ) if settings and settings.notify_favorite_category else 0


def publish_update_category_image(
    session_factory: Callable[[], Session], category_id: int, local_url: str
) -> None:
    with session_factory() as session:
        category = session.get(Category, category_id)
        if category is not None:
            category.box_art_url = local_url
            session.commit()


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


@dataclass(frozen=True)
class OnlineEvent:
    streamer_id: int
    username: str
    stream_id: int
    profile_image_url: str | None
    title: str | None
    category_name: str | None
    language: str | None
    new_stream: bool
    resume_recording: bool


def _online_snapshot(
    streamer: Streamer, stream: Stream, *, new_stream: bool, resume_recording: bool
) -> OnlineEvent:
    return OnlineEvent(
        streamer_id=streamer.id,
        username=streamer.username,
        stream_id=stream.id,
        profile_image_url=streamer.profile_image_url,
        title=streamer.title,
        category_name=streamer.category_name,
        language=streamer.language,
        new_stream=new_stream,
        resume_recording=resume_recording,
    )


def prepare_online(
    session_factory: Callable[[], Session],
    data: Mapping[str, str],
    user_info: Mapping[str, object] | None,
    recording_enabled: Callable[[int], bool],
) -> OnlineEvent | None:
    with session_factory() as session:
        streamer = (
            session.query(Streamer)
            .filter(Streamer.twitch_id == data["broadcaster_user_id"])
            .first()
        )
        if streamer is None:
            return None
        existing = (
            session.query(Stream)
            .filter(
                Stream.streamer_id == streamer.id, Stream.twitch_stream_id == data["id"]
            )
            .first()
        )
        if existing is not None:
            resume = False
            if existing.ended_at is None and recording_enabled(streamer.id):
                active = (
                    session.query(Recording)
                    .filter(
                        Recording.stream_id == existing.id,
                        Recording.status == "recording",
                    )
                    .first()
                )
                resume = active is None
            return _online_snapshot(
                streamer, existing, new_stream=False, resume_recording=resume
            )
        if user_info:
            profile = user_info.get("profile_image_url")
            description = user_info.get("description")
            if isinstance(profile, str) and profile:
                streamer.profile_image_url = profile
            if isinstance(description, str) and description:
                streamer.description = description
        started_at = datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
        for stale in (
            session.query(Stream)
            .filter(Stream.streamer_id == streamer.id, Stream.ended_at.is_(None))
            .all()
        ):
            stale.ended_at = started_at
        stream = Stream(
            streamer_id=streamer.id,
            started_at=started_at,
            twitch_stream_id=data["id"],
            title=streamer.title,
            category_name=streamer.category_name,
            language=streamer.language,
        )
        session.add(stream)
        session.flush()
        session.add(
            StreamEvent(
                stream_id=stream.id,
                event_type="stream.online",
                title=streamer.title,
                category_name=streamer.category_name,
                language=streamer.language,
                timestamp=started_at,
            )
        )
        if streamer.category_name:
            session.add(
                StreamEvent(
                    stream_id=stream.id,
                    event_type="channel.update",
                    title=streamer.title,
                    category_name=streamer.category_name,
                    language=streamer.language,
                    timestamp=started_at - timedelta(seconds=1),
                )
            )
        streamer.is_live = True
        streamer.last_updated = datetime.now(timezone.utc)
        session.commit()
        return _online_snapshot(
            streamer, stream, new_stream=True, resume_recording=False
        )
