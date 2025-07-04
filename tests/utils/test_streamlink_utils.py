"""
Tests for the streamlink_utils module.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.utils.streamlink_utils import (
    get_streamlink_command,
    get_streamlink_vod_command,
    get_streamlink_clip_command,
    get_proxy_settings_from_db
)


class TestStreamlinkUtils:
    """Test the streamlink_utils module."""
    
    def test_get_streamlink_command_basic(self):
        """Test basic streamlink command generation."""
        cmd = get_streamlink_command(
            streamer_name="teststreamer",
            quality="best",
            output_path="/tmp/output.mp4",
            log_path="/tmp/streamlink.log"
        )
        
        # Check basic command structure
        assert cmd[0] == "streamlink"
        assert cmd[1] == "twitch.tv/teststreamer"
        assert cmd[2] == "best"
        assert "-o" in cmd
        assert "/tmp/output.ts" in cmd  # Should convert to .ts
        
        # Check important flags are present
        assert "--twitch-disable-ads" in cmd
        assert "--hls-live-restart" in cmd
        assert "--force" in cmd
        
        # Check log settings
        assert "--logfile" in cmd
        assert "/tmp/streamlink.log" in cmd
    
    def test_get_streamlink_command_with_proxy(self):
        """Test streamlink command with proxy settings."""
        proxy_settings = {
            "http": "http://proxy.example.com:8080",
            "https": "https://proxy.example.com:8443"
        }
        
        cmd = get_streamlink_command(
            streamer_name="teststreamer",
            quality="best",
            output_path="/tmp/output.mp4",
            proxy_settings=proxy_settings,
            log_path="/tmp/streamlink.log"
        )
        
        # Check proxy settings are included
        assert "--http-proxy" in cmd
        assert "http://proxy.example.com:8080" in cmd
        assert "--https-proxy" in cmd
        assert "https://proxy.example.com:8443" in cmd
        
        # Check proxy optimizations are included
        assert "--hls-segment-queue-threshold" in cmd
        assert "--ringbuffer-size" in cmd
        assert "512M" in cmd
    
    def test_get_streamlink_command_with_force_mode(self):
        """Test streamlink command with force mode enabled."""
        cmd = get_streamlink_command(
            streamer_name="teststreamer",
            quality="best",
            output_path="/tmp/output.mp4",
            force_mode=True,
            log_path="/tmp/streamlink.log"
        )
        
        # Find the index of --stream-segment-timeout
        timeout_idx = cmd.index("--stream-segment-timeout") + 1
        assert cmd[timeout_idx] == "45"  # Force mode increases timeout from 30 to 45
        
        # Find the index of --retry-open
        retry_idx = cmd.index("--retry-open") + 1
        assert cmd[retry_idx] == "8"  # Force mode increases retries from 5 to 8
    
    def test_get_streamlink_vod_command(self):
        """Test VOD download command generation."""
        with patch.dict(os.environ, {"FFMPEG_PATH": "/usr/bin/ffmpeg"}):
            cmd = get_streamlink_vod_command(
                video_id="123456789",
                quality="best",
                output_path="/tmp/vod.mp4"
            )
            
            assert cmd[0] == "streamlink"
            assert "--ffmpeg-ffmpeg" in cmd
            assert "/usr/bin/ffmpeg" in cmd
            assert "--url" in cmd
            assert "https://www.twitch.tv/videos/123456789" in cmd
    
    def test_get_streamlink_clip_command(self):
        """Test clip download command generation."""
        with patch.dict(os.environ, {"FFMPEG_PATH": "/usr/bin/ffmpeg"}):
            cmd = get_streamlink_clip_command(
                clip_url="https://clips.twitch.tv/test123",
                quality="best",
                output_path="/tmp/clip.mp4"
            )
            
            assert cmd[0] == "streamlink"
            assert "--url" in cmd
            assert "https://clips.twitch.tv/test123" in cmd
            assert "--default-stream" in cmd
            assert "best" in cmd
    
    @patch("app.utils.streamlink_utils.SessionLocal")
    def test_get_proxy_settings_from_db(self, mock_session):
        """Test getting proxy settings from the database."""
        # Set up mock
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        # Mock global settings
        mock_global_settings = MagicMock()
        mock_global_settings.http_proxy = "http://proxy.example.com:8080"
        mock_global_settings.https_proxy = "https://proxy.example.com:8443"
        mock_db.query.return_value.first.return_value = mock_global_settings
        
        # Call function
        proxy_settings = get_proxy_settings_from_db()
        
        # Check results
        assert proxy_settings["http"] == "http://proxy.example.com:8080"
        assert proxy_settings["https"] == "https://proxy.example.com:8443"

    def test_invalid_proxy_url(self):
        """Test validation of proxy URLs."""
        proxy_settings = {
            "http": "invalid-url"
        }
        
        with pytest.raises(ValueError, match="HTTP proxy URL must start with"):
            get_streamlink_command(
                streamer_name="teststreamer",
                quality="best",
                output_path="/tmp/output.mp4",
                proxy_settings=proxy_settings
            )
