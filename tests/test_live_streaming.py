"""
Tests for the Live Streaming Service.

Covers:
- Session lifecycle (create, lookup, cleanup)
- Command building (Streamlink + FFmpeg)
- HLS playlist serving
- Timeout and expiration logic
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from app.services.live_streaming_service import LiveStreamingService


@pytest.fixture
def service():
    return LiveStreamingService()


@pytest.mark.asyncio
async def test_build_streamlink_command(service):
    """Test that Streamlink command includes all required parameters"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy:
        
        mock_token_instance = MagicMock()
        mock_token_instance.get_valid_access_token.return_value = "test_token_123"
        mock_token.return_value = mock_token_instance
        
        mock_proxy.get_best_proxy.return_value = "http://proxy:8080"
        
        cmd = await service._build_streamlink_command("shroud", "best")
        
        assert "streamlink" in cmd[0]
        assert "https://twitch.tv/shroud" in cmd
        assert "best" in cmd
        assert "--twitch-api-header" in cmd
        assert "test_token_123" in cmd
        assert "--stdout" in cmd
        assert "--passthrough" in cmd
        assert "http://proxy:8080" in cmd


@pytest.mark.asyncio
async def test_session_lifecycle(service):
    """Test session creation, lookup, and deletion"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy, \
         patch('asyncio.create_subprocess_exec') as mock_proc:
        
        mock_token_instance = MagicMock()
        mock_token_instance.get_valid_access_token.return_value = "test_token"
        mock_token.return_value = mock_token_instance
        mock_proxy.get_best_proxy.return_value = None
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"")
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_proc.return_value = mock_process
        
        # Create session
        session = await service.create_session("test_streamer", "720p60")
        assert session is not None
        assert session.streamer_name == "test_streamer"
        assert session.quality == "720p60"
        
        # Lookup
        found = service.get_session(session.id)
        assert found is not None
        assert found.id == session.id
        
        # Delete
        await service.stop_session(session.id)
        assert service.get_session(session.id) is None


@pytest.mark.asyncio
async def test_session_timeout(service):
    """Test that inactive sessions are cleaned up"""
    with patch('app.services.live_streaming_service.TwitchTokenService') as mock_token, \
         patch('app.services.live_streaming_service.proxy_health_service') as mock_proxy, \
         patch('asyncio.create_subprocess_exec') as mock_proc:
        
        mock_token_instance = MagicMock()
        mock_token_instance.get_valid_access_token.return_value = "test_token"
        mock_token.return_value = mock_token_instance
        mock_proxy.get_best_proxy.return_value = None
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"")
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_proc.return_value = mock_process
        
        # Create session with very short timeout
        service.SESSION_TIMEOUT_SECONDS = 1
        session = await service.create_session("test_streamer", "best")
        
        # Simulate timeout
        await asyncio.sleep(1.5)
        
        # Run cleanup
        expired = await service.cleanup_expired_sessions()
        assert session.id in expired
        assert service.get_session(session.id) is None


def test_is_safe_path(service):
    """Test path traversal prevention"""
    assert service._is_safe_path("playlist.m3u8", session_id="abc123") is True
    assert service._is_safe_path("segment_0.ts", session_id="abc123") is True
    assert service._is_safe_path("../../../etc/passwd", session_id="abc123") is False
    assert service._is_safe_path("segment_0.ts/../../etc/passwd", session_id="abc123") is False


@pytest.mark.asyncio
async def test_generate_hls_playlist(service):
    """Test HLS playlist generation"""
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        session = MagicMock()
        session.hls_dir = tmpdir
        session.quality = "best"
        session.streamer_name = "test"
        session.created_at = datetime.utcnow()
        
        # Create dummy segment files
        for i in range(3):
            open(os.path.join(tmpdir, f"segment_{i}.ts"), "w").close()
        
        playlist = await service._generate_hls_playlist(session)
        
        assert "#EXTM3U" in playlist
        assert "#EXT-X-VERSION:3" in playlist
        assert "#EXT-X-TARGETDURATION:5" in playlist
        assert "segment_0.ts" in playlist
        assert "segment_1.ts" in playlist
        assert "segment_2.ts" in playlist
        assert "#EXT-X-ENDLIST" not in playlist  # Live streams don't end
