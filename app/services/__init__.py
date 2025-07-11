"""
StreamVault Services Module.

This module exports all available services in the StreamVault application.
"""

# Import the new modular RecordingService implementation to make it available at the old import path
from app.services.recording.recording_service import RecordingService

# Re-export other services to maintain consistent imports
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService
from app.services.streamer_service import StreamerService
from app.services.logging_service import LoggingService
from app.services.metadata_service import MetadataService
from app.services.enhanced_push_service import EnhancedPushService
from app.services.media_server_structure_service import MediaServerStructureService
from app.services.cleanup_service import CleanupService
from app.services.settings_service import SettingsService
from app.services.category_image_service import CategoryImageService
from app.services.system_config_service import SystemConfigService
from app.services.test_service import StreamVaultTestService
