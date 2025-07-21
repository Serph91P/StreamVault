"""
TaskProgressTracker - Progress tracking and WebSocket updates

Extracted from background_queue_service.py God Class
Handles progress updates, statistics, and WebSocket notifications.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger("streamvault")

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class QueueTask:
    """Background task definition"""
    id: str
    task_type: str
    priority: TaskPriority
    payload: Dict[str, Any]
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    progress: float = 0.0
    
    def __lt__(self, other):
        """Enable comparison for PriorityQueue"""
        if not isinstance(other, QueueTask):
            return NotImplemented
        # Compare by created_at timestamp for FIFO ordering of same priority tasks
        return self.created_at < other.created_at
    
    def __eq__(self, other):
        """Enable equality comparison"""
        if not isinstance(other, QueueTask):
            return NotImplemented
        return self.id == other.id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization"""
        return {
            **asdict(self),
            'priority': self.priority.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskProgressTracker:
    """Handles task progress tracking and WebSocket notifications"""
    
    def __init__(self, websocket_manager=None):
        self.websocket_manager = websocket_manager
        self.active_tasks: Dict[str, QueueTask] = {}
        self.completed_tasks: Dict[str, QueueTask] = {}
        self.external_tasks: Dict[str, QueueTask] = {}  # For external jobs like recordings
        
        # Task statistics
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'retried_tasks': 0
        }
        
        # Progress update callbacks
        self.progress_callbacks: Dict[str, Callable] = {}
        
        # Async task management for proper cleanup
        self.background_tasks: set = set()

    def _create_background_task(self, coro):
        """Create a background task with proper reference management"""
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    def add_task(self, task: QueueTask):
        """Add a task to tracking"""
        self.active_tasks[task.id] = task
        self.stats['total_tasks'] += 1
        logger.debug(f"Task {task.id} added to tracking")

    def update_task_status(self, task_id: str, status: TaskStatus, error_message: str = None):
        """Update task status"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            old_status = task.status
            task.status = status
            task.error_message = error_message
            
            if status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.now(timezone.utc)
                
                # Move to completed tasks
                self.completed_tasks[task_id] = self.active_tasks.pop(task_id)
                
                # Update statistics
                if status == TaskStatus.COMPLETED:
                    self.stats['completed_tasks'] += 1
                elif status == TaskStatus.FAILED:
                    self.stats['failed_tasks'] += 1
            elif status == TaskStatus.RETRYING:
                task.retry_count += 1
                self.stats['retried_tasks'] += 1
            
            logger.debug(f"Task {task_id} status updated: {old_status.value} -> {status.value}")
            
            # Send WebSocket update
            self._create_background_task(self._send_task_update(task))

    def update_task_progress(self, task_id: str, progress: float):
        """Update task progress"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            old_progress = task.progress
            task.progress = max(0.0, min(100.0, progress))
            
            logger.debug(f"Task {task_id} progress: {old_progress:.1f}% -> {task.progress:.1f}%")
            
            # Call progress callback if registered
            if task_id in self.progress_callbacks:
                try:
                    self.progress_callbacks[task_id](task.progress)
                except Exception as e:
                    logger.warning(f"Progress callback failed for task {task_id}: {e}")
            
            # Send WebSocket update (throttled to avoid spam)
            if abs(task.progress - old_progress) >= 5.0 or task.progress >= 100.0:
                self._create_background_task(self._send_task_update(task))
                # Also send dedicated progress update for responsive UI
                self._create_background_task(self._send_progress_update(task_id, task.progress))

    def register_progress_callback(self, task_id: str, callback: Callable[[float], None]):
        """Register a progress callback for a task"""
        self.progress_callbacks[task_id] = callback

    def unregister_progress_callback(self, task_id: str):
        """Unregister a progress callback"""
        self.progress_callbacks.pop(task_id, None)

    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """Get task by ID"""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        if task_id in self.external_tasks:
            return self.external_tasks[task_id]
        return None

    def get_active_tasks(self) -> Dict[str, QueueTask]:
        """Get all active tasks"""
        return self.active_tasks.copy()

    def get_completed_tasks(self) -> Dict[str, QueueTask]:
        """Get all completed tasks"""
        return self.completed_tasks.copy()

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status"""
        task = self.get_task(task_id)
        return task.status if task else None

    def get_task_progress(self, task_id: str) -> Optional[float]:
        """Get task progress"""
        task = self.get_task(task_id)
        return task.progress if task else None

    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics"""
        # Count tasks by status
        pending_tasks = len([t for t in self.active_tasks.values() if t.status == TaskStatus.PENDING])
        running_tasks = len([t for t in self.active_tasks.values() if t.status == TaskStatus.RUNNING])
        
        return {
            **self.stats,
            'active_tasks': len(self.active_tasks) + len(self.external_tasks),
            'pending_tasks': pending_tasks,
            'running_tasks': running_tasks,
            'external_tasks': len(self.external_tasks),
            'workers': 0,  # Will be updated by worker manager if needed
            'is_running': True
        }

    # External task tracking methods (for recordings, etc.)
    
    def add_external_task(self, task_id: str, task_type: str, payload: Dict[str, Any]):
        """Add an external task for tracking (like recordings)"""
        task = QueueTask(
            id=task_id,
            task_type=task_type,
            priority=TaskPriority.NORMAL,
            payload=payload,
            status=TaskStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc)
        )
        self.external_tasks[task_id] = task
        logger.debug(f"External task {task_id} ({task_type}) added to tracking")

    def update_external_task_progress(self, task_id: str, progress: float):
        """Update external task progress"""
        if task_id in self.external_tasks:
            task = self.external_tasks[task_id]
            old_progress = task.progress
            task.progress = max(0.0, min(100.0, progress))
            
            logger.debug(f"External task {task_id} progress: {old_progress:.1f}% -> {task.progress:.1f}%")
            
            # Send WebSocket update
            if abs(task.progress - old_progress) >= 5.0 or task.progress >= 100.0:
                self._create_background_task(self._send_task_update(task))

    def complete_external_task(self, task_id: str, success: bool = True):
        """Mark external task as completed"""
        if task_id in self.external_tasks:
            task = self.external_tasks[task_id]
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100.0 if success else task.progress
            
            logger.debug(f"External task {task_id} marked as {'completed' if success else 'failed'}")
            
            # Send final WebSocket update
            self._create_background_task(self._send_task_update(task))

    def remove_external_task(self, task_id: str):
        """Remove external task from tracking"""
        if task_id in self.external_tasks:
            del self.external_tasks[task_id]
            logger.debug(f"External task {task_id} removed from tracking")

    async def cleanup_background_tasks(self):
        """Cancel all background tasks"""
        if self.background_tasks:
            logger.debug(f"Cancelling {len(self.background_tasks)} background tasks")
            for task in self.background_tasks:
                task.cancel()
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            self.background_tasks.clear()

    # WebSocket notification methods
    
    async def _send_task_update(self, task: QueueTask):
        """Send task update via WebSocket"""
        if not self.websocket_manager:
            return
            
        try:
            message = {
                "type": "task_status_update",
                "data": {
                    "id": task.id,
                    "task_type": task.task_type,
                    "status": task.status.value,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "error_message": task.error_message,
                    "retry_count": task.retry_count,
                    "payload": task.payload
                }
            }
            
            await self.websocket_manager.send_notification(message)
            
        except Exception as e:
            logger.warning(f"Failed to send WebSocket task update for {task.id}: {e}")

    async def _send_progress_update(self, task_id: str, progress: float):
        """Send dedicated progress update via WebSocket"""
        if not self.websocket_manager:
            return
            
        try:
            message = {
                "type": "task_progress_update",
                "data": {
                    "task_id": task_id,
                    "progress": progress
                }
            }
            
            await self.websocket_manager.send_notification(message)
            
        except Exception as e:
            logger.warning(f"Failed to send WebSocket progress update for {task_id}: {e}")

    async def send_queue_statistics(self):
        """Send queue statistics via WebSocket"""
        if not self.websocket_manager:
            return
            
        try:
            stats = self.get_statistics()
            message = {
                "type": "queue_stats_update",
                "data": stats
            }
            
            await self.websocket_manager.send_notification(message)
            
        except Exception as e:
            logger.warning(f"Failed to send WebSocket queue statistics: {e}")

    # Cleanup methods
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        # Clean completed tasks
        to_remove = []
        for task_id, task in self.completed_tasks.items():
            if task.completed_at and task.completed_at.timestamp() < cutoff_time:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.completed_tasks[task_id]
            
        # Clean external tasks
        to_remove = []
        for task_id, task in self.external_tasks.items():
            if task.completed_at and task.completed_at.timestamp() < cutoff_time:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.external_tasks[task_id]
            
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")

    def clear_all_tasks(self):
        """Clear all tasks (for shutdown)"""
        self.active_tasks.clear()
        self.completed_tasks.clear()
        self.external_tasks.clear()
        self.progress_callbacks.clear()
        logger.debug("All tasks cleared from tracker")
