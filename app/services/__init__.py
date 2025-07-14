"""
StreamVault Services Module.

This module exports all available services in the StreamVault application.
"""

from app.services.recording.recording_service import RecordingService
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.file_operations import (
    find_and_validate_mp4,
    intelligent_ts_cleanup,
    check_ffmpeg_processes_for_file
)
from app.services.recording.notification_manager import NotificationManager
from app.services.recording.stream_info_manager import StreamInfoManager
from app.services.recording.exceptions import (
    RecordingError, ProcessError, ConfigurationError, 
    StreamUnavailableError, FileOperationError
)

from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService
from app.services.streamer_service import StreamerService
from app.services.logging_service import LoggingService
from app.services.metadata_service import MetadataService
from app.services.enhanced_push_service import EnhancedPushService
from app.services.cleanup_service import CleanupService
from app.services.settings_service import SettingsService
from app.services.category_image_service import CategoryImageService
from app.services.migration_service import MigrationService
from app.services.thumbnail_service import ThumbnailService
from app.services.artwork_service import ArtworkService
from app.services.system_config_service import SystemConfigService
from app.services.twitch_auth_service import TwitchAuthService
from app.services.webpush_service import WebPushService
from app.services.websocket_manager import ConnectionManager

__all__ = [
    "LoggingService",
    "RecordingService",
    "StreamerService",
    "NotificationService",
    "MetadataService",
    "AuthService",
    "CategoryImageService",
    "MigrationService",
    "CleanupService",
    "EnhancedPushService",
    "SettingsService",
    "ThumbnailService",
    "ArtworkService",
    "SystemConfigService",
    "TwitchAuthService",
    "WebPushService",
    "ConnectionManager",
    "ConfigManager",
    "ProcessManager",
    "RecordingLogger",
    "NotificationManager",
    "StreamInfoManager",
    "intelligent_ts_cleanup",
    "check_ffmpeg_processes_for_file",
    "find_and_validate_mp4",
    "RecordingError",
    "ProcessError",
    "ConfigurationError",
    "StreamUnavailableError",
    "FileOperationError"
]
