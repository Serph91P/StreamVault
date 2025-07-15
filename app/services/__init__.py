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
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService
from app.services.streamer_service import StreamerService
from app.services.logging_service import LoggingService
from app.services.metadata_service import MetadataService
from app.services.enhanced_push_service import EnhancedPushService
from app.services.cleanup_service import CleanupService
from app.services.settings_service import SettingsService
# Removed: CategoryImageService - now handled by unified_image_service
from app.services.migration_service import MigrationService
from app.services.thumbnail_service import ThumbnailService
from app.services.artwork_service import ArtworkService
from app.services.system_config_service import SystemConfigService
from app.services.twitch_auth_service import TwitchAuthService
from app.services.webpush_service import ModernWebPushService  # Changed to correct class name
from app.services.websocket_manager import ConnectionManager
from app.services.unified_image_service import UnifiedImageService

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
    "ModernWebPushService",  # Changed from WebPushService
    "ConnectionManager",
    "UnifiedImageService",
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
