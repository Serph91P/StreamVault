"""
StreamVault Services Module.

This module exports all available services in the StreamVault application.
"""

# Import the new modular RecordingService implementation to make it available at the old import path
from app.services.recording.recording_service import RecordingService
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.file_operations import (
    intelligent_ts_cleanup,
    check_ffmpeg_processes_for_file
)
from app.services.recording.notification_manager import NotificationManager
from app.services.recording.stream_info_manager import StreamInfoManager
from app.services.recording.exceptions import (
    RecordingError, ProcessError, ConfigurationError, 
    StreamUnavailableError, FileOperationError
)

# Re-export other services to maintain consistent imports
from app.services.core.auth_service import AuthService
from app.services.notification_service import NotificationService
from app.services.streamer_service import StreamerService
from app.services.system.logging_service import LoggingService
from app.services.media.metadata_service import MetadataService
from app.services.communication.webpush_service import ModernWebPushService
from app.services.system.cleanup_service import CleanupService
from app.services.core.settings_service import SettingsService
# Removed: CategoryImageService - now handled by unified_image_service
from app.services.system.migration_service import MigrationService
from app.services.media.thumbnail_service import ThumbnailService
from app.services.media.artwork_service import ArtworkService
from app.services.system.system_config_service import SystemConfigService
from app.services.api.twitch_oauth_service import TwitchOAuthService
from app.services.communication.webpush_service import ModernWebPushService  # Changed to correct class name
from app.services.communication.websocket_manager import ConnectionManager
from app.services.unified_image_service import UnifiedImageService
from app.services.process_monitor import ProcessMonitor, process_monitor

__all__ = [
    "LoggingService",
    "RecordingService",
    "StreamerService",
    "NotificationService",
    "MetadataService",
    "AuthService",

    "MigrationService",
    "CleanupService",
    "ModernWebPushService",
    "SettingsService",
    "ThumbnailService",
    "ArtworkService",
    "SystemConfigService",
    "TwitchOAuthService",
    "ModernWebPushService",  # Changed from WebPushService
    "ConnectionManager",
    "UnifiedImageService",
    "ProcessMonitor",
    "process_monitor",
    # Export recording components
    "ConfigManager",
    "ProcessManager",
    "RecordingLogger",
    "NotificationManager",
    "StreamInfoManager",
    # Export file operations functions
    "intelligent_ts_cleanup",
    "check_ffmpeg_processes_for_file",
    # Export exceptions
    "RecordingError",
    "ProcessError",
    "ConfigurationError",
    "StreamUnavailableError",
    "FileOperationError"
]

# Note: test_service is not imported here to avoid circular imports
