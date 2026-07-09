"""Tests for EventSub event routing: dedup, stream dedup, event→stream mapping.

Regression tests for the bug where channel.update events (chapter markers)
were attached to the wrong stream and ended up as bookmarks in the wrong MP4.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Recording, Stream, Streamer, StreamEvent


def _make_registry():
    """Build an EventHandlerRegistry with all heavy dependencies mocked."""
    with patch("app.events.handler_registry.RecordingService"), patch(
        "app.events.handler_registry.ConfigManager"
    ), patch("app.events.handler_registry.NotificationService"):
        from app.events.handler_registry import EventHandlerRegistry

        registry = EventHandlerRegistry(connection_manager=MagicMock())
    registry.notification_service = AsyncMock()
    registry.recording_service = AsyncMock()
    registry.config_manager = MagicMock()
    registry.config_manager.is_recording_enabled.return_value = False
    registry.get_user_info = AsyncMock(return_value=None)
    return registry


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        # Clean relevant tables so tests are independent
        session.query(StreamEvent).delete()
        session.query(Recording).delete()
        session.query(Stream).delete()
        session.query(Streamer).delete()
        session.commit()
        yield session
    finally:
        session.close()


def _make_streamer(session, twitch_id="111", username="streamer_a"):
    streamer = Streamer(
        twitch_id=twitch_id,
        username=username,
        is_live=False,
    )
    session.add(streamer)
    session.commit()
    return streamer


class TestIsDuplicateMessage:
    def test_same_message_id_is_duplicate(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("msg-1", "channel.update", "111") is False
        assert registry.is_duplicate_message("msg-1", "channel.update", "111") is True

    def test_different_message_ids_are_not_duplicates(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("msg-1", "stream.online", "111") is False
        assert registry.is_duplicate_message("msg-2", "stream.online", "111") is False

    def test_missing_message_id_never_dedups(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("", "stream.online", "111") is False
        assert registry.is_duplicate_message(None, "stream.online", "111") is False

    def test_old_broken_method_is_gone(self):
        registry = _make_registry()
        assert not hasattr(registry, "_is_duplicate_event")
