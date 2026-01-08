"""
Pytest configuration and fixtures for StreamVault tests.

This file sets up the test environment with appropriate paths and database configuration.
"""

import os
import sys
import tempfile
from pathlib import Path

# Set environment variables BEFORE any imports from app modules
# This is critical to avoid the LoggingService trying to create /app/logs
# and the ImageService trying to create /recordings

# Use a temporary directory for all test directories
_test_temp_dir = tempfile.mkdtemp(prefix="streamvault_test_")

# Log directories
os.environ.setdefault("LOG_DIR", os.path.join(_test_temp_dir, "logs"))
os.environ.setdefault("STREAMLINK_LOG_DIR", os.path.join(_test_temp_dir, "logs", "streamlink"))
os.environ.setdefault("FFMPEG_LOG_DIR", os.path.join(_test_temp_dir, "logs", "ffmpeg"))
os.environ.setdefault("APP_LOG_DIR", os.path.join(_test_temp_dir, "logs", "app"))
os.environ.setdefault("LOGS_BASE_DIR", os.path.join(_test_temp_dir, "logs"))

# Recording and media directories (critical for image services)
os.environ.setdefault("RECORDING_DIRECTORY", os.path.join(_test_temp_dir, "recordings"))
os.environ.setdefault("ARTWORK_BASE_PATH", os.path.join(_test_temp_dir, "recordings", ".artwork"))

# Create all the directories
_test_dirs = [
    os.environ.get("LOG_DIR"),
    os.environ.get("STREAMLINK_LOG_DIR"),
    os.environ.get("FFMPEG_LOG_DIR"),
    os.environ.get("APP_LOG_DIR"),
    os.environ.get("RECORDING_DIRECTORY"),
    os.environ.get("ARTWORK_BASE_PATH"),
    os.path.join(_test_temp_dir, "recordings", ".media"),
]

for dir_path in _test_dirs:
    if dir_path:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

# Ensure we use SQLite for testing if no DATABASE_URL is set
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Set required Twitch credentials for testing (mock values)
os.environ.setdefault("TWITCH_APP_ID", "test_app_id")
os.environ.setdefault("TWITCH_APP_SECRET", "test_app_secret")
os.environ.setdefault("BASE_URL", "http://localhost:8000")

import pytest
import shutil


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Session-scoped fixture to set up and clean up the test environment."""
    # Create local logs directory if it doesn't exist
    local_logs = Path("logs_local")
    local_logs.mkdir(parents=True, exist_ok=True)
    (local_logs / "streamlink").mkdir(parents=True, exist_ok=True)
    (local_logs / "ffmpeg").mkdir(parents=True, exist_ok=True)
    (local_logs / "app").mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Cleanup temp directory after all tests
    if os.path.exists(_test_temp_dir):
        shutil.rmtree(_test_temp_dir, ignore_errors=True)


@pytest.fixture
def temp_logs_dir(tmp_path):
    """Provide a temporary logs directory for individual tests."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "streamlink").mkdir(parents=True, exist_ok=True)
    (logs_dir / "ffmpeg").mkdir(parents=True, exist_ok=True)
    (logs_dir / "app").mkdir(parents=True, exist_ok=True)
    return logs_dir


@pytest.fixture
def temp_recordings_dir(tmp_path):
    """Provide a temporary recordings directory for individual tests."""
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    (recordings_dir / ".media").mkdir(parents=True, exist_ok=True)
    (recordings_dir / ".artwork").mkdir(parents=True, exist_ok=True)
    return recordings_dir
