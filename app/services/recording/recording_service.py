"""
RecordingService - Backward compatibility wrapper

This is a lightweight wrapper around the refactored recording services
to maintain backward compatibility while the codebase migrates to the new structure.

Original ULTRA-BOSS God Class (1084 lines) split into:
- RecordingOrchestrator: Central coordinator and main entry point
- RecordingStateManager: Active recordings tracking and persistence
- RecordingDatabaseService: Database operations and session management
- RecordingWebSocketService: Real-time WebSocket communications
- PostProcessingCoordinator: File processing and post-processing workflows
- RecordingLifecycleManager: Recording start/stop lifecycle management
"""

import logging
from typing import Dict, Any, Optional, List
from .recording_orchestrator import RecordingOrchestrator

logger = logging.getLogger("streamvault")


class RecordingService:
    """Backward compatibility wrapper for the refactored recording services"""
    
    def __init__(self, db=None):
        # Initialize the orchestrator which manages all refactored services
        self.orchestrator = RecordingOrchestrator(db)
        
        # Legacy properties for compatibility
        self.db = self.orchestrator.database_service.db
        self.config_manager = self.orchestrator.config_manager
        self.process_manager = self.orchestrator.process_manager
        self.recording_logger = self.orchestrator.recording_logger
        self.notification_manager = self.orchestrator.notification_manager
        self.stream_info_manager = self.orchestrator.stream_info_manager
        self.logging_service = self.orchestrator.logging_service
        
        # Legacy state properties
        self.active_recordings = self.orchestrator.state_manager.active_recordings
        self.recording_tasks = self.orchestrator.state_manager.recording_tasks
        self.max_concurrent_recordings = self.orchestrator.state_manager.max_concurrent_recordings
        self.recordings_directory = self.orchestrator.config_manager.get_recordings_directory()
        
        # Legacy shutdown properties
        self._shutdown_event = self.orchestrator.lifecycle_manager._shutdown_event
        self._is_shutting_down = False

    # Main API methods (delegate to orchestrator)

    async def start_recording(self, stream_id: int, streamer_id: int, **kwargs) -> Optional[int]:
        """Start a new recording - main entry point"""
        return await self.orchestrator.start_recording(stream_id, streamer_id, **kwargs)

    async def stop_recording(self, recording_id: int, reason: str = "manual") -> bool:
        """Stop an active recording"""
        return await self.orchestrator.stop_recording(recording_id, reason)

    async def force_start_recording(self, streamer_id: int) -> Optional[int]:
        """Force start recording for a live streamer"""
        return await self.orchestrator.force_start_recording(streamer_id)

    def get_active_recordings(self) -> Dict[int, Dict[str, Any]]:
        """Get all active recordings"""
        return self.orchestrator.get_active_recordings()

    async def send_active_recordings_websocket_update(self) -> None:
        """Send active recordings update via WebSocket"""
        await self.orchestrator.send_active_recordings_websocket_update()

    # Database methods (delegate to orchestrator)

    async def update_recording_status(
        self, recording_id: int, status: str, path: str = None, duration_seconds: int = None
    ) -> None:
        """Update recording status in database"""
        await self.orchestrator.update_recording_status(recording_id, status, path, duration_seconds)

    async def ensure_stream_ended(self, stream_id: int) -> None:
        """Ensure stream is marked as ended"""
        await self.orchestrator.ensure_stream_ended(stream_id)

    # Recovery methods (delegate to orchestrator)

    async def recover_active_recordings_from_persistence(self) -> List[int]:
        """Recover active recordings from persistence after restart"""
        return await self.orchestrator.recover_active_recordings_from_persistence()

    # Post-processing methods (delegate to orchestrator)

    async def enqueue_post_processing(
        self, recording_id: int, ts_file_path: str, recording_data: Dict[str, Any]
    ) -> bool:
        """Enqueue post-processing for completed recording"""
        return await self.orchestrator.enqueue_post_processing(recording_id, ts_file_path, recording_data)

    async def find_and_validate_mp4(self, ts_file_path: str, max_wait_minutes: int = 10) -> Optional[str]:
        """Find and validate converted MP4 file"""
        return await self.orchestrator.find_and_validate_mp4(ts_file_path, max_wait_minutes)

    # Management methods (delegate to orchestrator)

    def cleanup_finished_tasks(self) -> List[int]:
        """Clean up finished recording tasks"""
        return self.orchestrator.cleanup_finished_tasks()

    async def cleanup_all_recordings(self) -> List[int]:
        """Stop all active recordings"""
        return await self.orchestrator.cleanup_all_recordings()

    def get_recording_statistics(self) -> Dict[str, Any]:
        """Get comprehensive recording statistics"""
        return self.orchestrator.get_recording_statistics()

    # Shutdown methods (delegate to orchestrator)

    async def graceful_shutdown(self) -> None:
        """Gracefully shutdown all recording operations"""
        self._is_shutting_down = True
        await self.orchestrator.graceful_shutdown()

    def is_shutting_down(self) -> bool:
        """Check if shutting down"""
        return self._is_shutting_down or self.orchestrator.is_shutting_down()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete"""
        await self.orchestrator.wait_for_shutdown()

    # Legacy methods for backward compatibility

    def _ensure_db_session(self):
        """Legacy method - handled by database service"""
        self.orchestrator.database_service._ensure_db_session()

    async def _update_recording_status(self, recording_id: int, status: str, path: str, duration_seconds: int):
        """Legacy method - delegate to database service"""
        await self.orchestrator.update_recording_status(recording_id, status, path, duration_seconds)

    async def _ensure_stream_ended(self, stream_id: int):
        """Legacy method - delegate to database service"""
        await self.orchestrator.ensure_stream_ended(stream_id)

    async def _monitor_and_process_recording(self, recording_id: int):
        """Legacy method - delegate to lifecycle manager"""
        await self.orchestrator.lifecycle_manager.monitor_and_process_recording(recording_id)

    async def _enqueue_post_processing(self, recording_id: int, ts_file_path: str, recording_data: Dict[str, Any]):
        """Legacy method - delegate to post-processing coordinator"""
        await self.orchestrator.enqueue_post_processing(recording_id, ts_file_path, recording_data)

    async def _find_and_validate_mp4(self, ts_file_path: str, max_wait_minutes: int = 10):
        """Legacy method - delegate to post-processing coordinator"""
        return await self.orchestrator.find_and_validate_mp4(ts_file_path, max_wait_minutes)

    async def _send_recording_job_update(self, recording_id: int, job_type: str, status: str, progress: float = 0.0):
        """Legacy method - delegate to websocket service"""
        await self.orchestrator.websocket_service.send_recording_job_update(recording_id, job_type, status, progress)

    async def _send_background_task_update(self, task_id: str, task_type: str, status: str, progress: float = 0.0):
        """Legacy method - delegate to websocket service"""
        await self.orchestrator.websocket_service.send_background_task_update(task_id, task_type, status, progress)

    async def _force_stop_all_recordings(self):
        """Legacy method - delegate to cleanup"""
        await self.orchestrator.cleanup_all_recordings()

    def _cancel_all_tasks(self):
        """Legacy method - delegate to state manager"""
        return self.orchestrator.state_manager.cancel_all_tasks()

    async def _delayed_metadata_generation(self, recording_id: int, delay_minutes: int = 5):
        """Legacy method - delegate to post-processing coordinator"""
        await self.orchestrator.post_processing_coordinator.delayed_metadata_generation(recording_id, delay_minutes)

    async def _generate_stream_metadata(self, recording_id: int, stream_data: Dict[str, Any]):
        """Legacy method - delegate to post-processing coordinator"""
        return await self.orchestrator.post_processing_coordinator.generate_stream_metadata(recording_id, stream_data)

    async def _recover_single_recording(self, recording_id: int, recording_data: Dict[str, Any]):
        """Legacy method - handled by state manager"""
        return await self.orchestrator.state_manager._recover_single_recording(
            recording_id, recording_data, self.orchestrator.database_service
        )

    # Legacy properties for backward compatibility

    @property
    def active_recording_count(self) -> int:
        """Get count of active recordings"""
        return self.orchestrator.state_manager.get_active_recording_count()

    @property
    def can_start_new_recording(self) -> bool:
        """Check if new recording can be started"""
        return self.orchestrator.state_manager.can_start_new_recording()

    @property
    def is_at_max_capacity(self) -> bool:
        """Check if at maximum capacity"""
        return self.orchestrator.state_manager.is_at_max_capacity()

    # Additional helper methods for legacy compatibility

    def get_active_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get active recording data"""
        return self.orchestrator.state_manager.get_active_recording(recording_id)

    def add_active_recording(self, recording_id: int, recording_data: Dict[str, Any]) -> None:
        """Add recording to active tracking"""
        self.orchestrator.state_manager.add_active_recording(recording_id, recording_data)

    def remove_active_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Remove recording from active tracking"""
        return self.orchestrator.state_manager.remove_active_recording(recording_id)

    async def save_state_to_persistence(self) -> None:
        """Save active recordings state to persistence"""
        await self.orchestrator.state_manager.save_state_to_persistence()

    def clear_all_state(self) -> None:
        """Clear all state (for shutdown)"""
        self.orchestrator.state_manager.clear_all_state()
