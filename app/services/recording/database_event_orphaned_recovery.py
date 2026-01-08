"""
Database Event Triggered Orphaned Recovery

This service listens to database events and triggers orphaned recovery
when recordings are updated to certain states that might indicate
orphaned .ts files needing post-processing.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("streamvault")


class DatabaseEventOrphanedRecovery:
    """Handles orphaned recovery triggered by database events"""

    def __init__(self):
        self.last_check: Optional[datetime] = None
        self.min_check_interval_minutes = 15  # Minimum 15 minutes between checks

    async def on_recording_status_changed(self, recording_id: int, old_status: str, new_status: str):
        """Handle recording status change events"""
        try:
            # Trigger orphaned check when recordings are marked as stopped/failed
            # but might have orphaned .ts files
            if new_status in ["stopped", "failed"] and old_status in ["active", "recording"]:
                logger.info(f"🔍 RECORDING_STATUS_CHANGED: {recording_id} {old_status} -> {new_status}")

                # Check if we should run orphaned recovery (rate limiting)
                if self._should_run_orphaned_check():
                    await self._trigger_orphaned_recovery_check("recording_status_change")

        except Exception as e:
            logger.error(f"Error handling recording status change: {e}", exc_info=True)

    async def on_recording_created(self, recording_id: int, recording_data: Dict[str, Any]):
        """Handle new recording creation events"""
        try:
            # When new recordings are created, it might indicate previous recordings
            # were not properly processed
            logger.debug(f"🔍 RECORDING_CREATED: {recording_id}")

            # Only check occasionally to avoid spam
            if self._should_run_orphaned_check():
                await self._trigger_orphaned_recovery_check("recording_created")

        except Exception as e:
            logger.error(f"Error handling recording creation: {e}", exc_info=True)

    async def on_stream_ended(self, stream_id: int, stream_data: Dict[str, Any]):
        """Handle stream end events"""
        try:
            logger.debug(f"🔍 STREAM_ENDED: {stream_id}")

            # When streams end, check for orphaned recordings
            # This catches cases where recording processes died but streams continued
            if self._should_run_orphaned_check():
                await self._trigger_orphaned_recovery_check("stream_ended")

        except Exception as e:
            logger.error(f"Error handling stream end: {e}", exc_info=True)

    async def on_post_processing_completed(self, recording_id: int, task_type: str):
        """Handle post-processing task completion"""
        try:
            logger.debug(f"🔍 POST_PROCESSING_COMPLETED: {recording_id} - {task_type}")

            # FIXED: Don't trigger orphaned recovery after every post-processing completion
            # This was causing continuous orphaned recovery checks
            # Orphaned recovery should only run:
            # 1. Once at startup
            # 2. When explicitly triggered via API
            # 3. When streams end (to catch failed recordings)
            logger.debug(f"✅ POST_PROCESSING_COMPLETED: {task_type} for recording {recording_id} - no orphaned check needed")

        except Exception as e:
            logger.error(f"Error handling post-processing completion: {e}", exc_info=True)

    def _should_run_orphaned_check(self) -> bool:
        """Check if enough time has passed to run another orphaned recovery check"""
        if self.last_check is None:
            return True

        time_since_last = datetime.utcnow() - self.last_check
        return time_since_last.total_seconds() > (self.min_check_interval_minutes * 60)

    async def _trigger_orphaned_recovery_check(self, trigger_reason: str):
        """Trigger an orphaned recovery check via background queue"""
        try:
            self.last_check = datetime.utcnow()

            logger.info(f"🔍 TRIGGERING_ORPHANED_RECOVERY_CHECK: reason={trigger_reason}")

            # Import background queue service
            try:
                from app.services.background_queue_service import background_queue_service

                if background_queue_service and background_queue_service.is_running:
                    await background_queue_service.enqueue_task(
                        "orphaned_recovery_check",
                        {
                            "max_age_hours": 48,  # Check recordings from last 48 hours
                            "trigger_reason": trigger_reason
                        },
                        priority=1  # Low priority
                    )
                    logger.debug(f"🔍 ORPHANED_RECOVERY_CHECK_SCHEDULED: {trigger_reason}")
                else:
                    logger.debug("Background queue service not available for orphaned recovery check")

            except Exception as e:
                logger.debug(f"Could not schedule orphaned recovery check: {e}")

        except Exception as e:
            logger.error(f"Error triggering orphaned recovery check: {e}", exc_info=True)


# Global instance
_database_event_orphaned_recovery: Optional[DatabaseEventOrphanedRecovery] = None


def get_database_event_orphaned_recovery() -> DatabaseEventOrphanedRecovery:
    """Get singleton instance of DatabaseEventOrphanedRecovery"""
    global _database_event_orphaned_recovery

    if _database_event_orphaned_recovery is None:
        _database_event_orphaned_recovery = DatabaseEventOrphanedRecovery()

    return _database_event_orphaned_recovery


# Convenience functions for integration
async def on_recording_status_changed(recording_id: int, old_status: str, new_status: str):
    """Convenience function for recording status change events"""
    recovery_service = get_database_event_orphaned_recovery()
    await recovery_service.on_recording_status_changed(recording_id, old_status, new_status)


async def on_recording_created(recording_id: int, recording_data: Dict[str, Any]):
    """Convenience function for recording creation events"""
    recovery_service = get_database_event_orphaned_recovery()
    await recovery_service.on_recording_created(recording_id, recording_data)


async def on_stream_ended(stream_id: int, stream_data: Dict[str, Any]):
    """Convenience function for stream end events"""
    recovery_service = get_database_event_orphaned_recovery()
    await recovery_service.on_stream_ended(stream_id, stream_data)


async def on_post_processing_completed(recording_id: int, task_type: str):
    """Convenience function for post-processing completion events"""
    recovery_service = get_database_event_orphaned_recovery()
    await recovery_service.on_post_processing_completed(recording_id, task_type)
