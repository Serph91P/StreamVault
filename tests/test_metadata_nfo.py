"""Tests for NFO metadata generation helpers in metadata_service.

Covers:
- Series plot prefers streamer bio, falls back to placeholder.
- Actor thumb prefers HTTPS URL over local relative path.
- Historical categories are collected, de-duplicated and ordered.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.media.metadata_service import MetadataService


@pytest.fixture()
def service() -> MetadataService:
    return MetadataService()


# ---------------------------------------------------------------------------
# _series_plot_text
# ---------------------------------------------------------------------------

def test_series_plot_uses_streamer_bio(service: MetadataService) -> None:
    streamer = SimpleNamespace(
        username="gronkh",
        description="Streams by GRONKH – Let's Plays, Talks und mehr.",
    )
    assert (
        service._series_plot_text(streamer)
        == "Streams by GRONKH – Let's Plays, Talks und mehr."
    )


def test_series_plot_falls_back_when_bio_empty(service: MetadataService) -> None:
    streamer = SimpleNamespace(username="gronkh", description="")
    assert service._series_plot_text(streamer) == "Streams by gronkh on Twitch."


def test_series_plot_falls_back_when_bio_missing(service: MetadataService) -> None:
    streamer = SimpleNamespace(username="gronkh")  # no description attribute
    assert service._series_plot_text(streamer) == "Streams by gronkh on Twitch."


def test_series_plot_strips_whitespace(service: MetadataService) -> None:
    streamer = SimpleNamespace(username="g", description="   \n\t   ")
    assert service._series_plot_text(streamer) == "Streams by g on Twitch."


# ---------------------------------------------------------------------------
# _pick_actor_thumb_url
# ---------------------------------------------------------------------------

def test_actor_thumb_prefers_original_https_url(service: MetadataService, tmp_path: Path) -> None:
    streamer = SimpleNamespace(
        username="gronkh",
        profile_image_url="/recordings/.media/profiles/profile_avatar_1.jpg",
        original_profile_image_url="https://static-cdn.jtvnw.net/jtv_user_pictures/abc-300x300.png",
    )
    result = service._pick_actor_thumb_url(streamer, tmp_path, "gronkh")
    assert result == "https://static-cdn.jtvnw.net/jtv_user_pictures/abc-300x300.png"


def test_actor_thumb_uses_profile_image_url_when_http(
    service: MetadataService, tmp_path: Path
) -> None:
    streamer = SimpleNamespace(
        username="gronkh",
        profile_image_url="https://example.com/avatar.jpg",
        original_profile_image_url=None,
    )
    result = service._pick_actor_thumb_url(streamer, tmp_path, "gronkh")
    assert result == "https://example.com/avatar.jpg"


def test_actor_thumb_falls_back_to_relative_path(
    service: MetadataService, tmp_path: Path
) -> None:
    streamer = SimpleNamespace(
        username="gronkh",
        # Both point to a local cached file (not an http URL)
        profile_image_url="/recordings/.media/profiles/profile_avatar_1.jpg",
        original_profile_image_url="/recordings/.media/profiles/profile_avatar_1.jpg",
    )
    result = service._pick_actor_thumb_url(streamer, tmp_path, "gronkh")
    # Should return a relative path that ends with the cached poster filename
    assert result is not None
    assert result.endswith(".media/artwork/gronkh/poster.jpg")


# ---------------------------------------------------------------------------
# _collect_streamer_genres
# ---------------------------------------------------------------------------

def _build_mock_db(category_rows: list[tuple]) -> MagicMock:
    """Build a MagicMock Session that returns ``category_rows`` for the category query."""
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = category_rows
    return db


def test_collect_genres_from_streams(service: MetadataService) -> None:
    db = _build_mock_db([("Minecraft",), ("World of Warcraft",), ("Just Chatting",)])
    streamer = SimpleNamespace(
        id=1,
        username="dhalucard",
        category_name=None,
        last_stream_category_name=None,
    )
    assert service._collect_streamer_genres(db, streamer) == [
        "Minecraft",
        "World of Warcraft",
        "Just Chatting",
    ]


def test_collect_genres_deduplicates_case_insensitive(service: MetadataService) -> None:
    db = _build_mock_db(
        [("Minecraft",), ("minecraft",), ("  Minecraft  ",), ("Just Chatting",)]
    )
    streamer = SimpleNamespace(
        id=1,
        username="dhalucard",
        category_name=None,
        last_stream_category_name=None,
    )
    assert service._collect_streamer_genres(db, streamer) == [
        "Minecraft",
        "Just Chatting",
    ]


def test_collect_genres_includes_streamer_fallback_fields(service: MetadataService) -> None:
    db = _build_mock_db([])  # no historical rows
    streamer = SimpleNamespace(
        id=1,
        username="dhalucard",
        category_name="Just Chatting",
        last_stream_category_name="Minecraft",
    )
    assert service._collect_streamer_genres(db, streamer) == [
        "Just Chatting",
        "Minecraft",
    ]


def test_collect_genres_empty_when_nothing_known(service: MetadataService) -> None:
    db = _build_mock_db([])
    streamer = SimpleNamespace(
        id=1,
        username="dhalucard",
        category_name=None,
        last_stream_category_name=None,
    )
    assert service._collect_streamer_genres(db, streamer) == []


def test_collect_genres_respects_limit(service: MetadataService) -> None:
    many = [(f"Category {i}",) for i in range(30)]
    db = _build_mock_db(many)
    streamer = SimpleNamespace(
        id=1,
        username="x",
        category_name=None,
        last_stream_category_name=None,
    )
    result = service._collect_streamer_genres(db, streamer, limit=5)
    assert len(result) == 5
    assert result[0] == "Category 0"
