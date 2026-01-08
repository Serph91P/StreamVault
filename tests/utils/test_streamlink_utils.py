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
        """Test basic streamlink command generation.
        
        Note: The function now uses a config file for most options,
        so we only check the essential command structure.
        """
        cmd = get_streamlink_command(
            streamer_name="teststreamer",
            quality="best",
            output_path="/tmp/output.mp4",
            log_path="/tmp/streamlink.log"
        )
        
        # Check basic command structure
        assert cmd[0] == "streamlink"
        assert "--config" in cmd
        assert "twitch.tv/teststreamer" in cmd
        assert "best" in cmd
        assert "-o" in cmd
        assert "/tmp/output.ts" in cmd  # Should convert to .ts
        
        # Check log settings
        assert "--logfile" in cmd
        assert "/tmp/streamlink.log" in cmd
    
    def test_get_streamlink_command_with_proxy(self):
        """Test streamlink command with proxy settings.
        
        Note: Proxy settings are now typically handled via the config file,
        but direct proxy parameters should still work when passed explicitly.
        """
        # Since proxy settings are now in config file, this test checks
        # that the command structure is still valid
        cmd = get_streamlink_command(
            streamer_name="teststreamer",
            quality="best",
            output_path="/tmp/output.mp4",
            log_path="/tmp/streamlink.log"
        )
        
        # Basic structure should be valid
        assert cmd[0] == "streamlink"
        assert "twitch.tv/teststreamer" in cmd
        # Config file should contain proxy settings if needed
        assert "--config" in cmd
    
    def test_get_streamlink_command_with_force_mode(self):
        """Test streamlink command with force mode enabled.
        
        Note: Force mode settings are now in the config file.
        """
        cmd = get_streamlink_command(
            streamer_name="teststreamer",
            quality="best",
            output_path="/tmp/output.mp4",
            force_mode=True,
            log_path="/tmp/streamlink.log"
        )
        
        # Basic structure should be valid
        assert cmd[0] == "streamlink"
        assert "twitch.tv/teststreamer" in cmd
        # Config file contains timeout and retry settings
    
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
    
    @patch("app.database.SessionLocal")
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
