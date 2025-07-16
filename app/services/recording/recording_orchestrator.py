"""
RecordingOrchestrator - Central coordinator and main entry point

Extracted from recording_service.py ULTRA-BOSS (1084 lines)
Central coordinator that uses all other refactored services for recording operations.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
# websocket_manager will be imported when needed to avoid circular imports
from .recording_database_service import RecordingDatabaseService
from .recording_state_manager import RecordingStateManager
from .recording_websocket_service import RecordingWebSocketService
from .post_processing_coordinator import PostProcessingCoordinator
from .recording_lifecycle_manager import RecordingLifecycleManager

# Import managers (existing focused services)
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.notification_manager import NotificationManager
from app.services.recording.stream_info_manager import StreamInfoManager

logger = logging.getLogger("streamvault")


class RecordingOrchestrator:
    """Central coordinator for all recording operations"""
    
    def __init__(self, db=None):
        # Initialize existing managers
        self.config_manager = ConfigManager()
        self.process_manager = ProcessManager(config_manager=self.config_manager)
        self.recording_logger = RecordingLogger(config_manager=self.config_manager)
        self.notification_manager = NotificationManager(config_manager=self.config_manager)
        self.stream_info_manager = StreamInfoManager(config_manager=self.config_manager)
        
        # Initialize refactored services
        self.database_service = RecordingDatabaseService(db)
        self.state_manager = RecordingStateManager(self.config_manager)
        # Import websocket_manager here to avoid circular imports
        from app.dependencies import websocket_manager
        self.websocket_service = RecordingWebSocketService(websocket_manager)
        self.post_processing_coordinator = PostProcessingCoordinator(
            self.config_manager, self.websocket_service
        )
        self.lifecycle_manager = RecordingLifecycleManager(
            config_manager=self.config_manager,
            process_manager=self.process_manager,
            database_service=self.database_service,
            websocket_service=self.websocket_service,
            state_manager=self.state_manager
        )
        
        # Initialize logging service
        try:
            from app.services.system.logging_service import logging_service
            self.logging_service = logging_service
        except Exception as e:
            logger.warning(f"Could not initialize logging service: {e}")
            self.logging_service = None

    # Main public API methods (delegate to appropriate services)

    async def start_recording(self, stream_id: int, streamer_id: int, **kwargs) -> Optional[int]:
        """Start a new recording - main entry point"""
        return await self.lifecycle_manager.start_recording(stream_id, streamer_id, **kwargs)

    async def stop_recording(self, recording_id: int, reason: str = "manual") -> bool:
        """Stop an active recording"""
        return await self.lifecycle_manager.stop_recording(recording_id, reason)

    async def force_start_recording(self, streamer_id: int) -> Optional[int]:
        """Force start recording for a live streamer"""
        return await self.lifecycle_manager.force_start_recording(streamer_id)

    def get_active_recordings(self) -> Dict[int, Dict[str, Any]]:
        """Get all active recordings"""
        return self.state_manager.get_active_recordings()

    async def send_active_recordings_websocket_update(self) -> None:
        """Send active recordings update via WebSocket"""
        active_recordings = self.state_manager.get_active_recordings()
        await self.websocket_service.send_active_recordings_update(active_recordings)

    # Recovery and persistence methods

    async def recover_active_recordings_from_persistence(self) -> List[int]:
        """Recover active recordings from persistence after restart"""
        return await self.state_manager.recover_active_recordings_from_persistence(
            self.database_service
        )

    # Post-processing methods

    async def enqueue_post_processing(
        self, recording_id: int, ts_file_path: str, recording_data: Dict[str, Any]
    ) -> bool:
        """Enqueue post-processing for completed recording"""
        return await self.post_processing_coordinator.enqueue_post_processing(
            recording_id, ts_file_path, recording_data
        )

    async def find_and_validate_mp4(self, ts_file_path: str, max_wait_minutes: int = 10) -> Optional[str]:
        """Find and validate converted MP4 file"""
        return await self.post_processing_coordinator.find_and_validate_mp4(
            ts_file_path, max_wait_minutes
        )

    # Database operations (delegate to database service)

    async def update_recording_status(
        self, recording_id: int, status: str, path: str = None, duration_seconds: int = None
    ) -> None:
        """Update recording status in database"""
        await self.database_service.update_recording_status(
            recording_id, status, path, duration_seconds
        )

    async def ensure_stream_ended(self, stream_id: int) -> None:
        """Ensure stream is marked as ended"""
        await self.database_service.ensure_stream_ended(stream_id)

    # Management and monitoring methods

    def cleanup_finished_tasks(self) -> List[int]:
        """Clean up finished recording tasks"""
        return self.state_manager.cleanup_finished_tasks()

    async def cleanup_all_recordings(self) -> List[int]:
        """Stop all active recordings"""
        active_recordings = self.state_manager.get_active_recordings()
        stopped_recordings = []
        
        for recording_id in active_recordings:
            success = await self.stop_recording(recording_id, reason="cleanup")
            if success:
                stopped_recordings.append(recording_id)
        
        return stopped_recordings

    def get_recording_statistics(self) -> Dict[str, Any]:
        """Get comprehensive recording statistics"""
        base_stats = self.state_manager.get_recording_statistics()
        
        # Add additional statistics
        base_stats.update({
            'service_status': {
                'database_service': self.database_service is not None,
                'websocket_service': self.websocket_service.is_websocket_available(),
                'process_manager': self.process_manager is not None,
                'lifecycle_manager': not self.lifecycle_manager.is_shutting_down()
            }
        })
        
        return base_stats

    # Shutdown methods

    async def graceful_shutdown(self) -> None:
        """Gracefully shutdown all recording operations"""
        logger.info("Starting graceful shutdown of recording orchestrator")
        
        # Shutdown lifecycle manager (handles active recordings)
        await self.lifecycle_manager.graceful_shutdown()
        
        # Save state to persistence
        await self.state_manager.save_state_to_persistence()
        
        # Close database session
        self.database_service.close_session()
        
        # Clear all state
        self.state_manager.clear_all_state()
        
        logger.info("Recording orchestrator shutdown complete")

    def is_shutting_down(self) -> bool:
        """Check if shutting down"""
        return self.lifecycle_manager.is_shutting_down()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete"""
        await self.lifecycle_manager.wait_for_shutdown()

    # Legacy compatibility methods (delegate to appropriate services)

    def _ensure_db_session(self):
        """Legacy method - handled by database service"""
        self.database_service._ensure_db_session()

    async def _update_recording_status(self, recording_id: int, status: str, path: str, duration_seconds: int):
        """Legacy method - delegate to database service"""
        await self.database_service.update_recording_status(recording_id, status, path, duration_seconds)

    async def _ensure_stream_ended(self, stream_id: int):
        """Legacy method - delegate to database service"""
        await self.database_service.ensure_stream_ended(stream_id)

    async def _monitor_and_process_recording(self, recording_id: int):
        """Legacy method - delegate to lifecycle manager"""
        await self.lifecycle_manager.monitor_and_process_recording(recording_id)

    async def _enqueue_post_processing(self, recording_id: int, ts_file_path: str, recording_data: Dict[str, Any]):
        """Legacy method - delegate to post-processing coordinator"""
        await self.post_processing_coordinator.enqueue_post_processing(
            recording_id, ts_file_path, recording_data
        )

    async def _find_and_validate_mp4(self, ts_file_path: str, max_wait_minutes: int = 10):
        """Legacy method - delegate to post-processing coordinator"""
        return await self.post_processing_coordinator.find_and_validate_mp4(ts_file_path, max_wait_minutes)

    async def _send_recording_job_update(self, recording_id: int, job_type: str, status: str, progress: float = 0.0):
        """Legacy method - delegate to websocket service"""
        await self.websocket_service.send_recording_job_update(recording_id, job_type, status, progress)

    async def _send_background_task_update(self, task_id: str, task_type: str, status: str, progress: float = 0.0):
        """Legacy method - delegate to websocket service"""
        await self.websocket_service.send_background_task_update(task_id, task_type, status, progress)

    async def _force_stop_all_recordings(self):
        """Legacy method - delegate to cleanup"""
        await self.cleanup_all_recordings()

    def _cancel_all_tasks(self):
        """Legacy method - delegate to state manager"""
        return self.state_manager.cancel_all_tasks()

    async def _delayed_metadata_generation(self, recording_id: int, delay_minutes: int = 5):
        """Legacy method - delegate to post-processing coordinator"""
        await self.post_processing_coordinator.delayed_metadata_generation(recording_id, delay_minutes)

    async def _generate_stream_metadata(self, recording_id: int, stream_data: Dict[str, Any]):
        """Legacy method - delegate to post-processing coordinator"""
        return await self.post_processing_coordinator.generate_stream_metadata(recording_id, stream_data)

    async def _recover_single_recording(self, recording_id: int, recording_data: Dict[str, Any]):
        """Legacy method - handled by state manager"""
        return await self.state_manager._recover_single_recording(
            recording_id, recording_data, self.database_service
        )
