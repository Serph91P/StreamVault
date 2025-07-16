"""
Recording Package

Contains all recording-related services and managers:

Original focused managers:
- ConfigManager: Configuration management
- ProcessManager: Process execution management  
- RecordingLogger: Recording event logging
- NotificationManager: Notification handling
- StreamInfoManager: Stream metadata management

Refactored services (from original recording_service.py ULTRA-BOSS):
- RecordingOrchestrator: Central coordinator and main entry point
- RecordingStateManager: Active recordings tracking and persistence
- RecordingDatabaseService: Database operations and session management
- RecordingWebSocketService: Real-time WebSocket communications
- PostProcessingCoordinator: File processing and post-processing workflows
- RecordingLifecycleManager: Recording start/stop lifecycle management

Main entry point:
- RecordingService: Backward compatibility wrapper
"""

# Main service (backward compatibility wrapper)
from .recording_service import RecordingService

# Refactored services (new architecture)
from .recording_orchestrator import RecordingOrchestrator
from .recording_state_manager import RecordingStateManager
from .recording_database_service import RecordingDatabaseService
from .recording_websocket_service import RecordingWebSocketService
from .post_processing_coordinator import PostProcessingCoordinator
from .recording_lifecycle_manager import RecordingLifecycleManager

# Original focused managers (kept as-is)
from .config_manager import ConfigManager
from .process_manager import ProcessManager
from .recording_logger import RecordingLogger
from .notification_manager import NotificationManager
from .stream_info_manager import StreamInfoManager

__all__ = [
    # Main service
    'RecordingService',
    # Refactored services
    'RecordingOrchestrator',
    'RecordingStateManager', 
    'RecordingDatabaseService',
    'RecordingWebSocketService',
    'PostProcessingCoordinator',
    'RecordingLifecycleManager',
    # Original managers
    'ConfigManager',
    'ProcessManager',
    'RecordingLogger',
    'NotificationManager',
    'StreamInfoManager'
]
