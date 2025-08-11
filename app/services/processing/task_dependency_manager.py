"""
Task Dependency Manager for Background Queue
Manages task dependencies to ensure proper execution order
"""
import asyncio
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("streamvault")

class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    """Represents a task with dependencies"""
    id: str
    type: str  # 'metadata', 'chapters', 'mp4_remux', 'thumbnail', 'cleanup'
    payload: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 1  # Lower number = higher priority

class TaskDependencyManager:
    """Manages task dependencies and execution order"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self._shutdown = False
        
    async def add_task(self, task: Task) -> str:
        """Add a task to the dependency manager"""
        task_id = task.id
        
        # Validate dependencies exist
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                raise ValueError(f"Dependency {dep_id} not found for task {task_id}")
        
        self.tasks[task_id] = task
        logger.info(f"Added task {task_id} with dependencies: {task.dependencies}")
        
        # Check if task is immediately ready
        await self._update_task_status(task_id)
        
        return task_id
    
    async def _update_task_status(self, task_id: str):
        """Update task status based on dependencies"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        
        # Skip if already running/completed/failed
        if task.status in [TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return
            
        # Check if all dependencies are completed
        if all(dep_id in self.completed_tasks for dep_id in task.dependencies):
            task.status = TaskStatus.READY
            # Diagnostic: log detailed dependency satisfaction
            if task.dependencies:
                logger.info(
                    "🧩 TASK_READY: %s (deps satisfied: %s)",
                    task_id,
                    ",".join(sorted(task.dependencies))
                )
            else:
                logger.info("🧩 TASK_READY_NO_DEPS: %s", task_id)
        else:
            # Check if any dependency failed
            failed_deps = [dep_id for dep_id in task.dependencies if dep_id in self.failed_tasks]
            if failed_deps:
                task.status = TaskStatus.FAILED
                task.error = f"Dependencies failed: {failed_deps}"
                logger.error(f"Task {task_id} failed due to failed dependencies: {failed_deps}")
    
    async def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute, sorted by priority"""
        ready_tasks = [
            task for task in self.tasks.values() 
            if task.status == TaskStatus.READY
        ]
        
        # Sort by priority (lower number = higher priority), then by creation time
        ready_tasks.sort(key=lambda t: (t.priority, t.created_at))
        
        return ready_tasks
    
    async def mark_task_running(self, task_id: str):
        """Mark a task as running"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.RUNNING
            self.tasks[task_id].started_at = datetime.now()
            logger.info(f"Task {task_id} marked as running")
    
    async def mark_task_completed(self, task_id: str):
        """Mark a task as completed and update dependent tasks"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        
        self.completed_tasks.add(task_id)
        
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
        
        logger.info(f"Task {task_id} completed successfully")
        
        # Update status of dependent tasks
        await self._update_dependent_tasks(task_id)
    
    async def mark_task_failed(self, task_id: str, error: str):
        """Mark a task as failed and handle dependent tasks"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now()
        
        self.failed_tasks.add(task_id)
        
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
        
        logger.error(f"Task {task_id} failed: {error}")
        
        # Update status of dependent tasks (they will be marked as failed too)
        await self._update_dependent_tasks(task_id)
    
    async def _update_dependent_tasks(self, completed_task_id: str):
        """Update the status of tasks that depend on the completed task"""
        for task_id, task in self.tasks.items():
            if completed_task_id in task.dependencies:
                await self._update_task_status(task_id)
    
    async def retry_failed_task(self, task_id: str) -> bool:
        """Retry a failed task if retries are available"""
        if task_id not in self.tasks:
            return False
            
        task = self.tasks[task_id]
        
        if task.status != TaskStatus.FAILED:
            return False
            
        if task.retry_count >= task.max_retries:
            logger.warning(f"Task {task_id} has exceeded maximum retries ({task.max_retries})")
            return False
            
        task.retry_count += 1
        task.status = TaskStatus.PENDING
        task.error = None
        task.started_at = None
        task.completed_at = None
        
        # Remove from failed tasks
        self.failed_tasks.discard(task_id)
        
        logger.info(f"Retrying task {task_id} (attempt {task.retry_count}/{task.max_retries})")
        
        # Re-evaluate task status
        await self._update_task_status(task_id)
        
        return True
    
    async def cancel_task(self, task_id: str):
        """Cancel a task and its dependents"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        
        # Cancel running task
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        
        logger.info(f"Task {task_id} cancelled")
        
        # Cancel dependent tasks
        await self._cancel_dependent_tasks(task_id)
    
    async def _cancel_dependent_tasks(self, cancelled_task_id: str):
        """Cancel tasks that depend on the cancelled task"""
        for task_id, task in self.tasks.items():
            if cancelled_task_id in task.dependencies and task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                await self.cancel_task(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task"""
        if task_id in self.tasks:
            return self.tasks[task_id].status
        return None
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a task"""
        if task_id not in self.tasks:
            return None
            
        task = self.tasks[task_id]
        return {
            'id': task.id,
            'type': task.type,
            'status': task.status.value,
            'dependencies': list(task.dependencies),
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'error': task.error,
            'retry_count': task.retry_count,
            'max_retries': task.max_retries,
            'priority': task.priority
        }
    
    def get_all_tasks_info(self) -> List[Dict[str, Any]]:
        """Get information about all tasks"""
        return [self.get_task_info(task_id) for task_id in self.tasks.keys()]
    
    def get_task_chain_info(self, stream_id: int) -> Dict[str, Any]:
        """Get information about all tasks for a specific stream"""
        stream_tasks = [
            task for task in self.tasks.values()
            if task.payload.get('stream_id') == stream_id
        ]
        
        return {
            'stream_id': stream_id,
            'total_tasks': len(stream_tasks),
            'pending': len([t for t in stream_tasks if t.status == TaskStatus.PENDING]),
            'ready': len([t for t in stream_tasks if t.status == TaskStatus.READY]),
            'running': len([t for t in stream_tasks if t.status == TaskStatus.RUNNING]),
            'completed': len([t for t in stream_tasks if t.status == TaskStatus.COMPLETED]),
            'failed': len([t for t in stream_tasks if t.status == TaskStatus.FAILED]),
            'cancelled': len([t for t in stream_tasks if t.status == TaskStatus.CANCELLED]),
            'tasks': [self.get_task_info(task.id) for task in stream_tasks]
        }
    
    async def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Remove completed tasks older than max_age_hours"""
        now = datetime.now()
        to_remove = []
        
        for task_id, task in self.tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.completed_at:
                    age_hours = (now - task.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
            self.completed_tasks.discard(task_id)
            self.failed_tasks.discard(task_id)
            logger.debug(f"Cleaned up old task {task_id}")
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")
    
    async def shutdown(self):
        """Shutdown the dependency manager"""
        self._shutdown = True
        
        # Cancel all running tasks
        for task_id, async_task in self.running_tasks.items():
            logger.info(f"Cancelling running task {task_id}")
            async_task.cancel()
            
        # Wait for cancellation to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        
        self.running_tasks.clear()
        logger.info("Task dependency manager shut down")
