"""
Automatic Queue Recovery Service

Proactively monitors and recovers stuck tasks to prevent deadlocks
when multiple streams are running simultaneously.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.config.constants import ASYNC_DELAYS

logger = logging.getLogger("streamvault")


class AutomaticQueueRecoveryService:
    """Automatic recovery service for background queue tasks"""

    def __init__(self, background_queue_service=None):
        self.background_queue_service = background_queue_service
        self.is_running = False
        self.recovery_task: Optional[asyncio.Task] = None

        # Recovery thresholds - configurable via environment variables
        self.stuck_task_threshold_minutes = int(os.environ.get("STUCK_TASK_THRESHOLD_MINUTES", "5"))  # Consider tasks stuck after 5 minutes
        self.orphaned_check_threshold_minutes = int(os.environ.get("ORPHANED_CHECK_THRESHOLD_MINUTES", "2"))  # Stop orphaned checks after 2 minutes
        self.recovery_interval_seconds = int(os.environ.get("RECOVERY_INTERVAL_SECONDS", "30"))  # Check every 30 seconds

        # Statistics
        self.recovery_stats = {
            "total_recoveries": 0,
            "stuck_tasks_fixed": 0,
            "orphaned_checks_stopped": 0,
            "last_recovery": None
        }

    async def start(self):
        """Start the automatic recovery service"""
        if self.is_running:
            logger.debug("Automatic queue recovery already running")
            return

        self.is_running = True
        self.recovery_task = asyncio.create_task(self._recovery_worker())
        logger.info("🔄 Automatic queue recovery service started - monitoring every 30s")

    async def stop(self):
        """Stop the automatic recovery service"""
        if not self.is_running:
            return

        self.is_running = False

        if self.recovery_task:
            self.recovery_task.cancel()
            try:
                await self.recovery_task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Automatic queue recovery service stopped")

    async def _recovery_worker(self):
        """Main recovery worker that runs in background"""
        logger.info("🔄 Automatic recovery worker started")

        while self.is_running:
            try:
                # Run recovery checks
                recovery_result = await self._perform_recovery_check()

                if recovery_result["recovered"] > 0:
                    self.recovery_stats["total_recoveries"] += recovery_result["recovered"]
                    self.recovery_stats["last_recovery"] = datetime.now(timezone.utc).isoformat()
                    logger.info(f"🔧 AUTO_RECOVERY: Fixed {recovery_result['recovered']} issues automatically")

                # Wait before next check
                await asyncio.sleep(self.recovery_interval_seconds)

            except asyncio.CancelledError:
                logger.info("Automatic recovery worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in automatic recovery worker: {e}")
                await asyncio.sleep(ASYNC_DELAYS.AUTO_RECOVERY_ERROR_WAIT)

        logger.info("🛑 Automatic recovery worker stopped")

    async def _perform_recovery_check(self) -> Dict[str, Any]:
        """Perform automatic recovery check"""
        if not self.background_queue_service:
            return {"recovered": 0, "message": "No background queue service"}

        recovered_count = 0
        errors = []

        try:
            # Get current tasks
            external_tasks = getattr(self.background_queue_service, 'external_tasks', {})
            active_tasks = getattr(self.background_queue_service, 'active_tasks', {})

            now = datetime.now(timezone.utc)

            # Check external tasks for stuck recordings
            for task_id, task in list(external_tasks.items()):
                try:
                    if await self._should_recover_task(task, now):
                        if await self._recover_stuck_task(task_id, task):
                            recovered_count += 1
                            self.recovery_stats["stuck_tasks_fixed"] += 1
                except Exception as e:
                    errors.append(f"Failed to recover task {task_id}: {str(e)}")

            # Check active tasks for orphaned recovery checks
            for task_id, task in list(active_tasks.items()):
                try:
                    if await self._should_stop_orphaned_check(task, now):
                        if await self._stop_orphaned_check(task_id, task):
                            recovered_count += 1
                            self.recovery_stats["orphaned_checks_stopped"] += 1
                except Exception as e:
                    errors.append(f"Failed to stop orphaned check {task_id}: {str(e)}")

            return {
                "recovered": recovered_count,
                "errors": errors,
                "message": f"Automatic recovery: {recovered_count} issues fixed"
            }

        except Exception as e:
            logger.error(f"Error in automatic recovery check: {e}")
            return {"recovered": 0, "errors": [str(e)]}

    async def _should_recover_task(self, task, now: datetime) -> bool:
        """Check if a task should be recovered"""
        # Check if it's a recording task
        task_id = getattr(task, 'id', '')
        is_recording_task = (
            task_id.startswith('recording_')
            or (hasattr(task, 'task_type') and task.task_type == 'recording')
            or (hasattr(task, 'task_name') and 'recording' in str(task.task_name).lower())
        )

        if not is_recording_task:
            return False

        # Check task age
        task_created = getattr(task, 'created_at', None) or getattr(task, 'started_at', None)
        if not task_created:
            return False

        if task_created.tzinfo is None:
            task_created = task_created.replace(tzinfo=timezone.utc)

        task_age_minutes = (now - task_created).total_seconds() / 60

        # Check if task is stuck
        task_status = getattr(task, 'status', 'unknown')
        if hasattr(task_status, 'value'):
            status_value = task_status.value
        else:
            status_value = str(task_status).lower()

        # Heartbeat / last progress update support (added for safer recovery decisions)
        last_progress_update = getattr(task, 'last_progress_update', None)
        last_progress_minutes = None
        if last_progress_update:
            try:
                if last_progress_update.tzinfo is None:
                    last_progress_update = last_progress_update.replace(tzinfo=timezone.utc)
                last_progress_minutes = (now - last_progress_update).total_seconds() / 60
            except Exception:
                last_progress_minutes = None

        # Heuristic: consider a task "inactive" only if no heartbeat for > stuck_task_threshold_minutes
        no_recent_heartbeat = (
            last_progress_minutes is None
            or last_progress_minutes > self.stuck_task_threshold_minutes
        )

        # Extra safeguard: if progress is <100 and we still receive heartbeats (last update fresh), don't recover
        if last_progress_minutes is not None and last_progress_minutes <= self.stuck_task_threshold_minutes and task.progress < 100:
            return False

        # Recovery conditions (revised):
        # 1. Task at 100% but still RUNNING and age > threshold (likely missed completion event)
        if (
            hasattr(task, 'progress') and task.progress >= 100
            and status_value == 'running'
            and task_age_minutes > self.stuck_task_threshold_minutes
        ):
            return True

        # 2. Task RUNNING/PENDING for > 2 * threshold with no recent heartbeat
        if (
            status_value in ['running', 'pending']
            and task_age_minutes > self.stuck_task_threshold_minutes * 2
            and no_recent_heartbeat
        ):
            return True

        return False

    async def _should_stop_orphaned_check(self, task, now: datetime) -> bool:
        """Check if an orphaned recovery check should be stopped"""
        # Check if it's an orphaned recovery task
        task_id = getattr(task, 'id', '')
        is_orphaned_task = (
            (hasattr(task, 'task_type') and task.task_type == 'orphaned_recovery_check')
            or 'orphaned' in task_id.lower()
            or (hasattr(task, 'task_name') and 'orphaned' in str(task.task_name).lower())
        )

        if not is_orphaned_task:
            return False

        # Check task age
        task_created = getattr(task, 'created_at', None) or getattr(task, 'started_at', None)
        if not task_created:
            return False

        if task_created.tzinfo is None:
            task_created = task_created.replace(tzinfo=timezone.utc)

        task_age_minutes = (now - task_created).total_seconds() / 60

        # Stop orphaned checks running for more than threshold
        task_status = getattr(task, 'status', 'unknown')
        if hasattr(task_status, 'value'):
            status_value = task_status.value
        else:
            status_value = str(task_status).lower()

        if (status_value in ['running', 'pending']
                and task_age_minutes > self.orphaned_check_threshold_minutes):
            return True

        return False

    async def _recover_stuck_task(self, task_id: str, task) -> bool:
        """Recover a stuck task"""
        try:
            logger.info(f"🔧 AUTO_RECOVERY: Recovering stuck task {task_id}")

            # Mark as completed through proper channels
            if hasattr(self.background_queue_service, 'complete_external_task'):
                self.background_queue_service.complete_external_task(task_id, success=True)
                logger.info(f"✅ AUTO_RECOVERY: Marked {task_id} as completed")

            # Update task status directly
            if hasattr(task, 'status'):
                try:
                    from app.services.processing.task_dependency_manager import TaskStatus
                    if isinstance(task.status, TaskStatus):
                        task.status = TaskStatus.COMPLETED
                    else:
                        task.status = 'completed'
                except Exception as e:
                    logger.warning(f"Could not update task status directly: {e}")

            # Set completed timestamp
            if not hasattr(task, 'completed_at') or not task.completed_at:
                task.completed_at = datetime.now(timezone.utc)

            # Remove from external_tasks directly if needed
            external_tasks = getattr(self.background_queue_service, 'external_tasks', {})
            if task_id in external_tasks:
                del external_tasks[task_id]

            # Remove from progress tracking
            if hasattr(self.background_queue_service, 'progress_tracker'):
                try:
                    self.background_queue_service.progress_tracker.remove_external_task(task_id)
                except Exception as e:
                    logger.warning(f"Could not remove from progress tracker: {e}")

            return True

        except Exception as e:
            logger.error(f"Error recovering stuck task {task_id}: {e}")
            return False

    async def _stop_orphaned_check(self, task_id: str, task) -> bool:
        """Stop an orphaned recovery check"""
        try:
            logger.info(f"🛑 AUTO_RECOVERY: Stopping orphaned check {task_id}")

            # Complete the orphaned check task
            if hasattr(self.background_queue_service, 'queue_manager'):
                try:
                    await self.background_queue_service.queue_manager.mark_task_completed(task_id, success=True)
                except Exception as e:
                    logger.warning(f"Could not complete task via queue manager: {e}")

            # Update task status
            if hasattr(task, 'status'):
                try:
                    from app.services.processing.task_dependency_manager import TaskStatus
                    if isinstance(task.status, TaskStatus):
                        task.status = TaskStatus.COMPLETED
                    else:
                        task.status = 'completed'
                except Exception as e:
                    logger.warning(f"Could not update task status: {e}")

            # Set completed timestamp
            if not hasattr(task, 'completed_at') or not task.completed_at:
                task.completed_at = datetime.now(timezone.utc)

            # Remove from active_tasks directly
            active_tasks = getattr(self.background_queue_service, 'active_tasks', {})
            if task_id in active_tasks:
                del active_tasks[task_id]

            return True

        except Exception as e:
            logger.error(f"Error stopping orphaned check {task_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        return {
            **self.recovery_stats,
            "is_running": self.is_running,
            "thresholds": {
                "stuck_task_minutes": self.stuck_task_threshold_minutes,
                "orphaned_check_minutes": self.orphaned_check_threshold_minutes,
                "check_interval_seconds": self.recovery_interval_seconds
            }
        }


# Global instance
_recovery_service = None


def get_recovery_service():
    """Get singleton recovery service"""
    global _recovery_service

    if _recovery_service is None:
        try:
            from app.services.background_queue_service import background_queue_service
            _recovery_service = AutomaticQueueRecoveryService(background_queue_service)
        except Exception as e:
            logger.error(f"Failed to import background_queue_service: {e}")
            # Create service without background queue dependency for graceful degradation
            _recovery_service = AutomaticQueueRecoveryService(None)

    return _recovery_service
