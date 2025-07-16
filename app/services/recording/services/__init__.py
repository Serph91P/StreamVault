"""
Recording Services Package

Split from the original recording_service.py ULTRA-BOSS (1084 lines):
- RecordingOrchestrator: Central coordinator and main entry point
- RecordingStateManager: Active recordings tracking and persistence
- RecordingDatabaseService: Database operations and session management
- RecordingWebSocketService: Real-time WebSocket communications
- PostProcessingCoordinator: File processing and post-processing workflows
- RecordingLifecycleManager: Recording start/stop lifecycle management
"""

from .recording_orchestrator import RecordingOrchestrator
from .recording_state_manager import RecordingStateManager
from .recording_database_service import RecordingDatabaseService
from .recording_websocket_service import RecordingWebSocketService
from .post_processing_coordinator import PostProcessingCoordinator
from .recording_lifecycle_manager import RecordingLifecycleManager

__all__ = [
    'RecordingOrchestrator',
    'RecordingStateManager',
    'RecordingDatabaseService',
    'RecordingWebSocketService',
    'PostProcessingCoordinator',
    'RecordingLifecycleManager'
]
