"""Closed-session streamer values, not ORM identities or lazy relationships."""

from dataclasses import dataclass
from datetime import datetime

from app.models import Streamer


@dataclass(frozen=True, slots=True)
class StreamerSnapshot:
    id: int
    twitch_id: str
    username: str
    is_live: bool | None
    title: str | None
    category_name: str | None
    language: str | None
    last_updated: datetime | None
    profile_image_url: str | None
    original_profile_image_url: str | None
    offline_image_url: str | None
    original_offline_image_url: str | None
    description: str | None
    is_favorite: bool | None
    auto_record: bool | None
    created_at: datetime | None
    is_test_data: bool
    last_stream_title: str | None
    last_stream_category_name: str | None
    last_stream_viewer_count: int | None
    last_stream_ended_at: datetime | None
    is_recording: bool


def snapshot_streamer(row: Streamer) -> StreamerSnapshot:
    return StreamerSnapshot(
        id=row.id,
        twitch_id=row.twitch_id,
        username=row.username,
        is_live=row.is_live,
        title=row.title,
        category_name=row.category_name,
        language=row.language,
        last_updated=row.last_updated,
        profile_image_url=row.profile_image_url,
        original_profile_image_url=row.original_profile_image_url,
        offline_image_url=row.offline_image_url,
        original_offline_image_url=row.original_offline_image_url,
        description=row.description,
        is_favorite=row.is_favorite,
        auto_record=row.auto_record,
        created_at=row.created_at,
        is_test_data=row.is_test_data,
        last_stream_title=row.last_stream_title,
        last_stream_category_name=row.last_stream_category_name,
        last_stream_viewer_count=row.last_stream_viewer_count,
        last_stream_ended_at=row.last_stream_ended_at,
        is_recording=row.is_recording,
    )
