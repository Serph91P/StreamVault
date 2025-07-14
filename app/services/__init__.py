"""
StreamVault Services Module.

This module exports all available services in the StreamVault application.
"""

# Import the new modular RecordingService implementation to make it available at the old import path
from app.services.recording.recording_service import RecordingService
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.file_operations import find_and_validate_mp4, intelligent_ts_cleanup
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
from app.services.category_image_service import CategoryImageService
from app.services.system_config_service import SystemConfigService
from app.services.test_service import StreamVaultTestService
from app.services.migration_service import MigrationService
from app.services.proxy_service import ProxyService
from app.services.database_service import DatabaseService
from app.services.config_service import ConfigService
from app.services.stream_service import StreamService

__all__ = [
    "LoggingService",
    "RecordingService",
    "StreamerService",
    "NotificationService",
    "MetadataService",
    "ConfigService",
    "StreamService",
    "DatabaseService",
    "AuthService",
    "CategoryService",
    "MigrationService",
    "ProxyService",
    # Export file operations functions
    "intelligent_ts_cleanup",
    "find_and_validate_mp4"
]
