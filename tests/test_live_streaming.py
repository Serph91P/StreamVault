"""
Tests for the Live Streaming Service.

Covers:
- Session lifecycle (start, lookup, stop)
- Command building (Streamlink + FFmpeg)
- Session properties and timeout logic
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from app.services.live_streaming_service import LiveStreamingService, LiveStreamSession


@pytest.fixture
def service():
    svc = LiveStreamingService()
    svc.SESSION_TIMEOUT_SECONDS = 60
    return svc


@pytest.mark.asyncio
async def test_build_streamlink_command(service):
    """Test that Streamlink command includes all required parameters"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token_cls, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy, \
         patch('app.services.live_streaming_service.SessionLocal') as mock_db:

        mock_token = MagicMock()
        mock_token.get_valid_access_token = AsyncMock(return_value="test_token_123")
        mock_token_cls.return_value = mock_token

        mock_proxy.get_best_proxy = AsyncMock(return_value="http://proxy:8080")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_db.return_value = mock_session

        cmd = await service._build_streamlink_command("shroud", "best")

        assert "streamlink" in cmd[0]
        assert "twitch.tv/shroud" in cmd
        assert "best" in cmd
        assert "--twitch-api-header=Authorization=OAuth test_token_123" in cmd
        assert "--stdout" in cmd


@pytest.mark.asyncio
async def test_build_ffmpeg_command(service):
    """Test FFmpeg command structure"""
    from pathlib import Path
    output_dir = Path("/tmp/test-hls")
    cmd = service._build_ffmpeg_command(output_dir)

    assert "ffmpeg" in cmd[0]
    assert "-" in cmd  # stdin input
    assert "-f" in cmd
    assert "hls" in cmd
    assert "-hls_time" in cmd
    assert "-hls_list_size" in cmd
    assert str(output_dir / "playlist.m3u8") in cmd


@pytest.mark.asyncio
async def test_session_lifecycle(service):
    """Test session start, lookup, and stop"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token_cls, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy, \
         patch('app.services.live_streaming_service.SessionLocal') as mock_db, \
         patch('asyncio.create_subprocess_exec') as mock_proc:

        mock_token = MagicMock()
        mock_token.get_valid_access_token = AsyncMock(return_value="test_token")
        mock_token_cls.return_value = mock_token

        mock_proxy.get_best_proxy = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_db.return_value = mock_session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_proc.return_value = mock_process

        # Start session
        session_id = await service.start_stream("test_streamer", "720p60")
        assert session_id is not None
        assert len(session_id) == 8  # UUID[:8]

        # Lookup
        found = service.get_session(session_id)
        assert found is not None
        assert found.session_id == session_id
        assert found.streamer_name == "test_streamer"
        assert found.quality == "720p60"

        # Status
        status = service.get_session_status(session_id)
        assert status is not None
        assert status["streamer_name"] == "test_streamer"
        assert "/api/live/stream/" in status["playlist_url"]

        # Stop
        result = await service.stop_stream(session_id)
        assert result is True
        assert service.get_session(session_id) is None


@pytest.mark.asyncio
async def test_session_not_found(service):
    """Test operations on non-existent session"""
    assert service.get_session("nonexistent") is None
    assert service.get_session_status("nonexistent") is None
    result = await service.stop_stream("nonexistent")
    assert result is False


def test_session_expired():
    """Test session expiration logic"""
    session = LiveStreamSession(
        session_id="abc123",
        streamer_name="test",
        quality="best",
        streamlink_process=MagicMock(),
        ffmpeg_process=MagicMock(),
        output_dir=MagicMock(),
    )

    # Fresh session should not be expired
    assert session.is_expired(timeout_seconds=60) is False

    # Simulate old session
    session.last_accessed = datetime.utcnow() - __import__('datetime').timedelta(seconds=120)
    assert session.is_expired(timeout_seconds=60) is True


@pytest.mark.asyncio
async def test_max_concurrent_streams(service):
    """Test global concurrent stream limit"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token_cls, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy, \
         patch('app.services.live_streaming_service.SessionLocal') as mock_db, \
         patch('asyncio.create_subprocess_exec') as mock_proc:

        mock_token = MagicMock()
        mock_token.get_valid_access_token = AsyncMock(return_value="test_token")
        mock_token_cls.return_value = mock_token

        mock_proxy.get_best_proxy = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_db.return_value = mock_session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_proc.return_value = mock_process

        # Fill up to max
        session_ids = []
        for i in range(service.MAX_CONCURRENT_STREAMS):
            sid = await service.start_stream(f"streamer_{i}", "best")
            session_ids.append(sid)

        # Next one should fail
        with pytest.raises(RuntimeError, match="Maximum concurrent streams reached"):
            await service.start_stream("overflow", "best")

        # Cleanup
        for sid in session_ids:
            await service.stop_stream(sid)


@pytest.mark.asyncio
async def test_per_user_limit(service):
    """Test per-user concurrent stream limit"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token_cls, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy, \
         patch('app.services.live_streaming_service.SessionLocal') as mock_db, \
         patch('asyncio.create_subprocess_exec') as mock_proc:

        mock_token = MagicMock()
        mock_token.get_valid_access_token = AsyncMock(return_value="test_token")
        mock_token_cls.return_value = mock_token

        mock_proxy.get_best_proxy = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_db.return_value = mock_session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_proc.return_value = mock_process

        user_id = "user_123"
        s1 = await service.start_stream("streamer1", "best", user_id=user_id)
        s2 = await service.start_stream("streamer2", "best", user_id=user_id)

        # Third stream for same user should fail
        with pytest.raises(RuntimeError, match="Maximum 2 concurrent streams per user"):
            await service.start_stream("streamer3", "best", user_id=user_id)

        # Cleanup
        await service.stop_stream(s1)
        await service.stop_stream(s2)
