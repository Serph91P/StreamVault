"""Tests for EventSub event routing: dedup, stream dedup, event→stream mapping.

Regression tests for the bug where channel.update events (chapter markers)
were attached to the wrong stream and ended up as bookmarks in the wrong MP4.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Pre-existing circular import (app.services <-> app.events): importing
# app.events.handler_registry as the very first app import in a fresh process
# raises ImportError partway through and leaves sys.modules half-initialized
# (mock.patch then surfaces this as AttributeError). Importing app.services
# first follows the working initialization order — the same order production
# uses — after which handler_registry imports cleanly. Warm it up here so this
# file also passes when run in isolation.
import app.services  # noqa: F401
import app.events.handler_registry  # noqa: F401

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

    def test_forget_message_allows_retry_to_be_processed(self):
        registry = _make_registry()
        assert registry.is_duplicate_message("msg-1", "stream.online", "111") is False
        registry.forget_message("msg-1", "stream.online", "111")
        assert registry.is_duplicate_message("msg-1", "stream.online", "111") is False

    def test_forget_message_tolerates_unknown_fingerprint(self):
        registry = _make_registry()
        registry.forget_message("never-seen", "stream.online", "111")


class TestHandleStreamOnline:
    def _online_payload(self, twitch_stream_id="9001", broadcaster_id="111"):
        return {
            "id": twitch_stream_id,
            "broadcaster_user_id": broadcaster_id,
            "broadcaster_user_name": "streamer_a",
            "broadcaster_user_login": "streamer_a",
            "started_at": "2026-07-09T12:00:00Z",
        }

    def test_duplicate_online_does_not_create_second_stream(self, db):
        streamer = _make_streamer(db)
        registry = _make_registry()

        asyncio.run(registry.handle_stream_online(self._online_payload()))
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        streams = db.query(Stream).filter(Stream.streamer_id == streamer.id).all()
        assert len(streams) == 1

    def test_new_online_closes_stale_open_streams(self, db):
        streamer = _make_streamer(db)
        stale = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        db.add(stale)
        db.commit()
        stale_id = stale.id

        registry = _make_registry()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        db.expire_all()
        stale_row = db.query(Stream).filter(Stream.id == stale_id).first()
        assert stale_row.ended_at is not None
        # Stale streams are closed at the NEW stream's start time. SQLite
        # strips tzinfo on the round-trip, so compare against the naive
        # equivalent of 2026-07-09T12:00:00Z.
        assert stale_row.ended_at == datetime(2026, 7, 9, 12, 0)

        new_stream = (
            db.query(Stream).filter(Stream.twitch_stream_id == "9001").first()
        )
        assert new_stream is not None
        assert new_stream.ended_at is None

    def test_other_streamers_open_stream_is_not_closed(self, db):
        streamer_a = _make_streamer(db)
        streamer_b = _make_streamer(db, twitch_id="222", username="streamer_b")
        other_open = Stream(
            streamer_id=streamer_b.id,
            started_at=datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc),
            twitch_stream_id="7777",
        )
        db.add(other_open)
        db.commit()

        registry = _make_registry()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        db.expire_all()
        assert (
            db.query(Stream).filter(Stream.id == other_open.id).first().ended_at
            is None
        )

    def test_duplicate_online_resumes_missing_recording(self, db):
        streamer = _make_streamer(db)
        registry = _make_registry()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        existing = db.query(Stream).filter(Stream.twitch_stream_id == "9001").first()

        registry.config_manager.is_recording_enabled.return_value = True
        registry.recording_service.start_recording.reset_mock()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        registry.recording_service.start_recording.assert_awaited_once_with(
            existing.id, streamer.id, force_mode=False
        )
        assert (
            db.query(Stream).filter(Stream.streamer_id == streamer.id).count() == 1
        )

    def test_duplicate_online_with_active_recording_does_not_restart(self, db):
        streamer = _make_streamer(db)
        registry = _make_registry()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        existing = db.query(Stream).filter(Stream.twitch_stream_id == "9001").first()
        db.add(
            Recording(
                stream_id=existing.id,
                status="recording",
                start_time=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

        registry.config_manager.is_recording_enabled.return_value = True
        registry.recording_service.start_recording.reset_mock()
        asyncio.run(registry.handle_stream_online(self._online_payload()))

        registry.recording_service.start_recording.assert_not_awaited()


class TestHandleStreamUpdate:
    def _update_payload(self, broadcaster_id="111"):
        return {
            "broadcaster_user_id": broadcaster_id,
            "broadcaster_user_login": "streamer_a",
            "title": "New Title",
            "category_name": "New Game",
            "language": "de",
        }

    def test_event_attaches_to_actively_recorded_stream(self, db):
        """Two open streams; the OLDER one has the active recording.

        The chapter marker must go to the recorded stream, not the newest."""
        streamer = _make_streamer(db)
        recorded = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        orphan = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
            twitch_stream_id="9001",
        )
        db.add_all([recorded, orphan])
        db.commit()
        db.add(
            Recording(
                stream_id=recorded.id,
                status="recording",
                start_time=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

        registry = _make_registry()
        asyncio.run(registry.handle_stream_update(self._update_payload()))

        events = db.query(StreamEvent).filter(
            StreamEvent.event_type == "channel.update"
        ).all()
        assert len(events) == 1
        assert events[0].stream_id == recorded.id

    def test_fallback_to_latest_open_stream_without_recording(self, db):
        streamer = _make_streamer(db)
        older = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="8000",
        )
        newer = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
            twitch_stream_id="9001",
        )
        db.add_all([older, newer])
        db.commit()

        registry = _make_registry()
        asyncio.run(registry.handle_stream_update(self._update_payload()))

        events = db.query(StreamEvent).filter(
            StreamEvent.event_type == "channel.update"
        ).all()
        assert len(events) == 1
        assert events[0].stream_id == newer.id

    def test_unknown_broadcaster_is_ignored_without_error(self, db):
        registry = _make_registry()
        # Must not raise (previously: UnboundLocalError on `stream`)
        asyncio.run(registry.handle_stream_update(self._update_payload("999")))
        assert db.query(StreamEvent).count() == 0

    def test_zombie_recording_on_ended_stream_does_not_steal_events(self, db):
        """An ended stream with a stuck status='recording' row must not win
        over a genuinely open stream."""
        streamer = _make_streamer(db)
        zombie = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc),
            twitch_stream_id="7000",
        )
        live = Stream(
            streamer_id=streamer.id,
            started_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            twitch_stream_id="9001",
        )
        db.add_all([zombie, live])
        db.commit()
        db.add(
            Recording(
                stream_id=zombie.id,
                status="recording",
                start_time=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

        registry = _make_registry()
        asyncio.run(registry.handle_stream_update(self._update_payload()))

        events = db.query(StreamEvent).filter(
            StreamEvent.event_type == "channel.update"
        ).all()
        assert len(events) == 1
        assert events[0].stream_id == live.id
