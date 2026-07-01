"""
Tests for the Live Streaming Service.

Pure unit tests — no database imports, no pytest-asyncio.
Tests only logic that doesn't require external services.
"""

from unittest.mock import MagicMock
from datetime import datetime, timedelta


def test_live_stream_session_properties():
    """Test LiveStreamSession basic properties and expiration"""
    from app.services.live_streaming_service import LiveStreamSession

    session = LiveStreamSession(
        session_id="abc123",
        streamer_name="test_streamer",
        quality="best",
        streamlink_process=MagicMock(),
        ffmpeg_process=MagicMock(),
        output_dir=MagicMock(),
    )

    assert session.session_id == "abc123"
    assert session.streamer_name == "test_streamer"
    assert session.quality == "best"
    assert session.is_active is True

    # Fresh session not expired
    assert session.is_expired(timeout_seconds=60) is False

    # Simulate old session
    session.last_accessed = datetime.utcnow() - timedelta(seconds=120)
    assert session.is_expired(timeout_seconds=60) is True


def test_live_stream_session_touch():
    """Test touch() updates last_accessed"""
    from app.services.live_streaming_service import LiveStreamSession

    session = LiveStreamSession(
        session_id="abc123",
        streamer_name="test",
        quality="720p60",
        streamlink_process=MagicMock(),
        ffmpeg_process=MagicMock(),
        output_dir=MagicMock(),
    )

    old_accessed = session.last_accessed
    session.touch()
    assert session.last_accessed > old_accessed


def test_live_streaming_service_init():
    """Test service initialization"""
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    assert svc.SESSION_TIMEOUT_SECONDS == 60
    assert svc.MAX_CONCURRENT_STREAMS == 5
    assert svc.HLS_SEGMENT_DURATION == 2
    assert svc.HLS_LIST_SIZE == 10
    assert svc.sessions == {}
    assert svc.user_sessions == {}


def test_normalize_supported_codecs_for_live_playback():
    """Test live codec normalization keeps recordings config out of live playback."""
    from app.services.live_streaming_service import LiveStreamingService

    assert LiveStreamingService._normalize_supported_codecs("h264") == "h264"
    assert LiveStreamingService._normalize_supported_codecs("h264,h265") == "h264,h265"
    assert (
        LiveStreamingService._normalize_supported_codecs(" h265 , h264 ") == "h265,h264"
    )
    assert (
        LiveStreamingService._normalize_supported_codecs("h264,h264,h265")
        == "h264,h265"
    )
    assert LiveStreamingService._normalize_supported_codecs("vp9,unknown") == "h264"
    assert LiveStreamingService._normalize_supported_codecs("") == "h264"


def test_build_ffmpeg_command_structure():
    """Test FFmpeg command contains required arguments"""
    from app.services.live_streaming_service import LiveStreamingService
    from pathlib import Path

    svc = LiveStreamingService()
    output_dir = Path("/tmp/test-live")
    cmd = svc._build_ffmpeg_command(output_dir)

    assert cmd[0] == "ffmpeg"
    assert "-hide_banner" in cmd
    assert "-" in cmd  # stdin
    assert "-c" in cmd
    assert "copy" in cmd
    assert "-f" in cmd
    assert "hls" in cmd
    assert "-hls_time" in cmd
    assert "-hls_list_size" in cmd
    assert "-hls_flags" in cmd
    assert "delete_segments+omit_endlist" in cmd
    assert "-hls_segment_filename" in cmd
    assert str(output_dir / "playlist.m3u8") in cmd


def test_get_session_not_found():
    """Test get_session returns None for unknown session"""
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    assert svc.get_session("nonexistent") is None


def test_get_session_status_not_found():
    """Test get_session_status returns None for unknown session"""
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    assert svc.get_session_status("nonexistent") is None


def test_stop_stream_not_found():
    """Test stop_stream returns False for unknown session"""
    import asyncio
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    result = asyncio.run(svc.stop_stream("nonexistent"))
    assert result is False


def test_stop_existing_user_streams_replaces_same_streamer():
    """Test replacement cleanup only stops matching user/streamer sessions."""
    import asyncio
    from app.services.live_streaming_service import (
        LiveStreamingService,
        LiveStreamSession,
    )

    svc = LiveStreamingService()

    def make_session(session_id: str, streamer_name: str, user_id: str):
        streamlink_process = MagicMock()
        streamlink_process.returncode = 0
        ffmpeg_process = MagicMock()
        ffmpeg_process.returncode = 0
        output_dir = MagicMock()
        output_dir.exists.return_value = False
        return LiveStreamSession(
            session_id=session_id,
            streamer_name=streamer_name,
            quality="best",
            streamlink_process=streamlink_process,
            ffmpeg_process=ffmpeg_process,
            output_dir=output_dir,
            user_id=user_id,
        )

    svc.sessions = {
        "old": make_session("old", "HandOfBlood", "user-1"),
        "other-streamer": make_session("other-streamer", "maxim", "user-1"),
        "other-user": make_session("other-user", "HandOfBlood", "user-2"),
    }
    svc.user_sessions = {"user-1": {"old", "other-streamer"}, "user-2": {"other-user"}}

    asyncio.run(svc._stop_existing_user_streams("user-1", "handofblood"))

    assert "old" not in svc.sessions
    assert "old" not in svc.user_sessions["user-1"]
    assert "other-streamer" in svc.sessions
    assert "other-user" in svc.sessions
