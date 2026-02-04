"""
BackgroundQueueService - Backward compatibility wrapper

This is a lightweight wrapper around the refactored queue services
to maintain backward compatibility while the codebase migrates to the new structure.

Original God Class (613 lines) split into:
- TaskQueueManager: Core queue management and task orchestration
- WorkerManager: Worker thread management and task execution
- TaskProgressTracker: Progress tracking and WebSocket updates
"""

import logging
import warnings
from typing import Dict, Any, Optional, Callable
from .queues import TaskQueueManager
from .queues.task_progress_tracker import QueueTask, TaskStatus, TaskPriority

logger = logging.getLogger("streamvault")

# ProcessMonitor integration temporarily disabled for stability
process_monitor = None


class BackgroundQueueService:
    """Backward compatibility wrapper for the refactored queue services
    
    SINGLETON PATTERN: Use `background_queue_service` global instance.
    All parts of the application share the same queue to ensure consistent job tracking.
    """

    # Singleton instance tracking
    _instance: Optional["BackgroundQueueService"] = None
    _initialized: bool = False

    def __new__(cls, max_workers: int = 3, websocket_manager=None):
        """Singleton pattern - return existing instance if available"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_workers: int = 3, websocket_manager=None):
        # Only initialize once (singleton)
        if BackgroundQueueService._initialized:
            # Update websocket_manager if provided (for late binding)
            if websocket_manager is not None and hasattr(self, 'queue_manager'):
                self.queue_manager.progress_tracker.websocket_manager = websocket_manager
            return
            
        # Initialize the refactored queue manager with streamer isolation enabled for production
        self.queue_manager = TaskQueueManager(
            max_workers=max_workers,
            websocket_manager=websocket_manager,
            enable_streamer_isolation=True,  # Enable concurrent streaming by default
        )

        # Legacy properties for compatibility
        self.max_workers = max_workers
        # Handle both streamer isolation and shared queue modes
        if hasattr(self.queue_manager, "task_queue"):
            self.task_queue = self.queue_manager.task_queue
        else:
            # For streamer isolation mode, create a compatibility property
            self.task_queue = None
        self.active_tasks = self.queue_manager.progress_tracker.active_tasks
        self.completed_tasks = self.queue_manager.progress_tracker.completed_tasks
        self.external_tasks = self.queue_manager.progress_tracker.external_tasks
        self.workers = self.queue_manager.worker_manager.workers
        self.is_running = False
        self.task_handlers = self.queue_manager.worker_manager.task_handlers
        self.dependency_manager = self.queue_manager.dependency_manager
        self.dependency_worker = None
        self.stats = self.queue_manager.progress_tracker.stats
        
        BackgroundQueueService._initialized = True
        logger.debug("BackgroundQueueService singleton initialized")

    async def start(self):
        """Start the background queue service"""
        await self.queue_manager.start()
        self.is_running = self.queue_manager.is_running
        self.dependency_worker = self.queue_manager.dependency_worker

        # Start process monitor - temporarily disabled
        # if process_monitor:
        #     await process_monitor.start()

    async def stop(self):
        """Stop the background queue service"""
        await self.queue_manager.stop()
        self.is_running = self.queue_manager.is_running
        self.dependency_worker = self.queue_manager.dependency_worker

        # Stop process monitor - temporarily disabled
        # if process_monitor:
        #     await process_monitor.stop()

    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a handler for a specific task type"""
        self.queue_manager.register_task_handler(task_type, handler)

    async def enqueue_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ) -> str:
        """Enqueue a new background task"""
        return await self.queue_manager.enqueue_task(task_type, payload, priority, max_retries)

    async def enqueue_task_with_dependencies(
        self,
        task_type: str,
        payload: Dict[str, Any],
        dependencies: Optional[list] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ) -> str:
        """Enqueue a task with dependencies"""
        return await self.queue_manager.enqueue_task_with_dependencies(
            task_type, payload, dependencies, priority, max_retries
        )

    async def mark_task_completed(self, task_id: str, success: bool = True):
        """Mark a task as completed in dependency manager"""
        await self.queue_manager.mark_task_completed(task_id, success)

    # Status and progress methods (delegate to queue manager)

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status"""
        return self.queue_manager.get_task_status(task_id)

    def get_task_progress(self, task_id: str) -> Optional[float]:
        """Get task progress"""
        return self.queue_manager.get_task_progress(task_id)

    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """Get task by ID"""
        return self.queue_manager.get_task(task_id)

    def get_active_tasks(self) -> Dict[str, QueueTask]:
        """Get all active tasks including external tasks"""
        active_tasks = self.queue_manager.get_active_tasks()
        external_tasks = self.queue_manager.progress_tracker.external_tasks

        # Combine both dictionaries
        all_active_tasks = {**active_tasks, **external_tasks}
        return all_active_tasks

    def get_completed_tasks(self) -> Dict[str, QueueTask]:
        """Get all completed tasks"""
        return self.queue_manager.get_completed_tasks()

    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        queue_stats = self.queue_manager.get_queue_statistics()

        # Add process monitor statistics
        if process_monitor:
            try:
                process_stats = process_monitor.get_system_status()
                queue_stats.update(
                    {
                        "process_monitor": process_stats,
                        "active_processes": process_stats.get("active_processes", 0),
                        "recording_active": process_stats.get("recording_active", False),
                    }
                )
            except Exception as e:
                logger.warning(f"Could not get process monitor stats: {e}")

        return queue_stats

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics (async wrapper for API compatibility)"""
        return self.get_queue_statistics()

    async def get_recent_tasks(self, limit: int = 50) -> Dict[str, Any]:
        """Get recent completed tasks (async wrapper for API compatibility)"""
        completed_tasks = self.get_completed_tasks()
        # Convert to list and limit
        recent_list = list(completed_tasks.values())[-limit:]
        return {task.id: task for task in recent_list}

    async def send_queue_statistics(self):
        """Send queue statistics via WebSocket"""
        await self.queue_manager.send_queue_statistics()

        # Also send process monitor statistics - temporarily disabled
        # if process_monitor:
        #     try:
        #         await process_monitor.send_system_status()
        #     except Exception as e:
        #         logger.warning(f"Could not send process monitor stats: {e}")

    # External task tracking methods

    def add_external_task(self, task_id: str, task_type: str, payload: Dict[str, Any]):
        """Add an external task for tracking"""
        self.queue_manager.add_external_task(task_id, task_type, payload)

    def update_external_task_progress(self, task_id: str, progress: float):
        """Update external task progress"""
        self.queue_manager.update_external_task_progress(task_id, progress)

    def complete_external_task(self, task_id: str, success: bool = True):
        """Mark external task as completed"""
        self.queue_manager.complete_external_task(task_id, success)

    def remove_external_task(self, task_id: str):
        """Remove external task from tracking"""
        self.queue_manager.remove_external_task(task_id)

    # Legacy utility methods

    async def wait_for_completion(self, timeout: Optional[float] = None):
        """Wait for all current tasks to complete"""
        await self.queue_manager.wait_for_completion(timeout)

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        self.queue_manager.cleanup_old_tasks(max_age_hours)

    def clear_all_tasks(self):
        """Clear all tasks (for shutdown)"""
        self.queue_manager.clear_all_tasks()

    def get_registered_handlers(self) -> list:
        """Get list of registered task types"""
        return self.queue_manager.get_registered_handlers()

    def has_handler(self, task_type: str) -> bool:
        """Check if handler is registered for task type"""
        return self.queue_manager.has_handler(task_type)

    def has_queue_manager(self) -> bool:
        """Check if queue manager is available"""
        return hasattr(self, "queue_manager") and self.queue_manager is not None

    def is_queue_manager_running(self) -> bool:
        """Check if the queue manager is running"""
        return self.has_queue_manager() and self.queue_manager.is_running

    def get_queue_status(self) -> Optional[Dict[str, Any]]:
        """Get queue status with proper abstraction"""
        if not self.has_queue_manager():
            return None
        try:
            return self.queue_manager.get_queue_statistics()
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return None

    async def enqueue_recording_post_processing(self, **kwargs):
        """Enqueue a complete post-processing chain for a recording"""
        return await self.queue_manager.enqueue_recording_post_processing(**kwargs)

    # Properties for legacy compatibility

    @property
    def queue_size(self) -> int:
        """Get current queue size"""
        if self.task_queue:
            return self.task_queue.qsize()
        else:
            # For streamer isolation mode, sum all streamer queues
            stats = self.queue_manager.get_queue_statistics()
            return stats.get("queue_size", 0)

    @property
    def active_worker_count(self) -> int:
        """Get number of active workers"""
        return self.queue_manager.worker_manager.get_worker_count()

    @property
    def total_tasks_processed(self) -> int:
        """Get total number of tasks processed"""
        return self.stats["completed_tasks"] + self.stats["failed_tasks"]

    # Legacy methods that might be used by existing code

    def get_statistics(self) -> Dict[str, Any]:
        """Legacy method - use get_queue_statistics instead"""
        return self.get_queue_statistics()

    async def _worker(self, worker_name: str):
        """Legacy method - workers are now managed internally"""
        warnings.warn(
            "BackgroundQueueService._worker is deprecated. Workers are now managed internally by TaskQueueManager.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise NotImplementedError("Legacy _worker method is no longer supported")

    async def _dependency_worker(self):
        """Legacy method - dependency worker is now managed internally"""
        warnings.warn(
            "BackgroundQueueService._dependency_worker is deprecated. Dependency worker is now managed internally by TaskQueueManager.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise NotImplementedError("Legacy _dependency_worker method is no longer supported")


# Legacy exports for compatibility
TaskStatus = TaskStatus
TaskPriority = TaskPriority
QueueTask = QueueTask

# Global instance for backward compatibility
background_queue_service = BackgroundQueueService()
