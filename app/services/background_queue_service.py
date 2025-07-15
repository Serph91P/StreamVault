"""
Background Queue Service for Post-Processing Tasks

Handles long-running post-processing tasks like video conversion,
metadata generation, and thumbnail creation asynchronously.
Now includes dependency management for proper task execution order.
"""
import asyncio
import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid

from app.database import SessionLocal
from app.models import Stream, Recording
from app.utils.structured_logging import log_with_context
from app.services.task_dependency_manager import TaskDependencyManager, Task, TaskStatus as DepTaskStatus
from app.services.recording_task_factory import RecordingTaskFactory

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

class BackgroundQueueService:
    """Service for managing background post-processing tasks with dependency management"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.active_tasks: Dict[str, QueueTask] = {}
        self.completed_tasks: Dict[str, QueueTask] = {}
        self.workers: List[asyncio.Task] = []
        self.is_running = False
        self.task_handlers: Dict[str, Callable] = {}
        
        # Dependency management
        self.dependency_manager = TaskDependencyManager()
        self.dependency_worker: Optional[asyncio.Task] = None
        
        # Task statistics
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'retried_tasks': 0
        }
        
    async def start(self):
        """Start the background queue service"""
        if self.is_running:
            logger.warning("BackgroundQueueService already running")
            return
            
        self.is_running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
            
        # Start dependency worker
        self.dependency_worker = asyncio.create_task(self._dependency_worker())
            
        logger.info(f"BackgroundQueueService started with {self.max_workers} workers and dependency management")
        
    async def stop(self):
        """Stop the background queue service"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # Cancel dependency worker
        if self.dependency_worker:
            self.dependency_worker.cancel()
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
            
        # Wait for workers to finish
        all_workers = self.workers + ([self.dependency_worker] if self.dependency_worker else [])
        if all_workers:
            await asyncio.gather(*all_workers, return_exceptions=True)
            
        self.workers.clear()
        self.dependency_worker = None
        
        # Shutdown dependency manager
        await self.dependency_manager.shutdown()
        
        logger.info("BackgroundQueueService stopped")
        
    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a handler for a specific task type"""
        self.task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
        
    async def enqueue_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3
    ) -> str:
        """Enqueue a new background task"""
        
        task_id = str(uuid.uuid4())
        task = QueueTask(
            id=task_id,
            task_type=task_type,
            priority=priority,
            payload=payload,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            max_retries=max_retries
        )
        
        # Add to queue with priority (lower number = higher priority)
        await self.task_queue.put((-priority.value, task.created_at.timestamp(), task))
        
        self.stats['total_tasks'] += 1
        
        log_with_context(
            logger, 'info',
            f"Enqueued task {task_type}",
            task_id=task_id,
            task_type=task_type,
            priority=priority.name,
            operation='queue_enqueue'
        )
        
        return task_id
        
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task"""
        # Check active tasks first
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].to_dict()
            
        # Check completed tasks
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id].to_dict()
            
        return None
        
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            **self.stats,
            'pending_tasks': self.task_queue.qsize(),
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'workers': len(self.workers),
            'is_running': self.is_running
        }
        
    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get all currently active tasks"""
        return [task.to_dict() for task in self.active_tasks.values()]
        
    async def get_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent completed tasks"""
        # Sort by completion time (most recent first)
        sorted_tasks = sorted(
            self.completed_tasks.values(),
            key=lambda x: x.completed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        # Return the most recent tasks up to the limit
        return [task.to_dict() for task in sorted_tasks[:limit]]
        
    async def _worker(self, worker_name: str):
        """Background worker that processes tasks from the queue"""
        logger.info(f"Worker {worker_name} started")
        
        try:
            while self.is_running:
                try:
                    # Get task from queue with timeout
                    priority, timestamp, task = await asyncio.wait_for(
                        self.task_queue.get(), 
                        timeout=1.0
                    )
                    
                    # Process the task
                    await self._process_task(task, worker_name)
                    
                except asyncio.TimeoutError:
                    # No task available, continue
                    continue
                except Exception as e:
                    logger.error(f"Worker {worker_name} error: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info(f"Worker {worker_name} cancelled")
        except Exception as e:
            logger.error(f"Worker {worker_name} crashed: {e}", exc_info=True)
        finally:
            logger.info(f"Worker {worker_name} stopped")
            

                    
    async def _retry_task_after_delay(self, task: QueueTask, delay: float):
        """Retry a task after a delay"""
        await asyncio.sleep(delay)
        
        # Reset task status
        task.status = TaskStatus.PENDING
        task.started_at = None
        task.progress = 0.0
        
        # Re-enqueue
        await self.task_queue.put((-task.priority.value, task.created_at.timestamp(), task))

    async def _dependency_worker(self):
        """Worker that manages task dependencies and feeds ready tasks to the main queue"""
        logger.info("Dependency worker started")
        
        try:
            while self.is_running:
                try:
                    # Get ready tasks from dependency manager
                    ready_tasks = await self.dependency_manager.get_ready_tasks()
                    
                    # Convert dependency tasks to queue tasks and enqueue
                    for dep_task in ready_tasks:
                        # Mark as running in dependency manager
                        await self.dependency_manager.mark_task_running(dep_task.id)
                        
                        # Convert to QueueTask
                        queue_task = QueueTask(
                            id=dep_task.id,
                            task_type=dep_task.type,
                            priority=TaskPriority(dep_task.priority),
                            payload=dep_task.payload,
                            status=TaskStatus.PENDING,
                            created_at=dep_task.created_at,
                            max_retries=dep_task.max_retries
                        )
                        
                        # Add to processing queue with unique tiebreaker
                        await self.task_queue.put((-queue_task.priority.value, queue_task.created_at.timestamp(), queue_task))
                        
                        logger.debug(f"Dependency worker enqueued ready task: {dep_task.id}")
                    
                    # Sleep briefly to avoid busy waiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Dependency worker error: {e}", exc_info=True)
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            logger.info("Dependency worker cancelled")
        except Exception as e:
            logger.error(f"Dependency worker crashed: {e}", exc_info=True)
        finally:
            logger.info("Dependency worker stopped")

    # High-level methods for recording post-processing
    async def enqueue_recording_post_processing(
        self,
        stream_id: int,
        recording_id: int,
        ts_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str,
        cleanup_ts_file: bool = True
    ) -> List[str]:
        """Enqueue a complete post-processing chain for a recording
        
        Returns:
            List of task IDs in the chain
        """
        # Create task chain using factory
        tasks = RecordingTaskFactory.create_post_processing_chain(
            stream_id=stream_id,
            recording_id=recording_id,
            ts_file_path=ts_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at,
            cleanup_ts_file=cleanup_ts_file
        )
        
        # Add tasks to dependency manager
        task_ids = []
        for task in tasks:
            await self.dependency_manager.add_task(task)
            task_ids.append(task.id)
            
        logger.info(f"Enqueued recording post-processing chain for stream {stream_id} with {len(tasks)} tasks")
        
        return task_ids

    async def enqueue_metadata_generation(
        self,
        stream_id: int,
        recording_id: int,
        mp4_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str
    ) -> List[str]:
        """Enqueue metadata generation tasks for an existing MP4 file
        
        Returns:
            List of task IDs
        """
        # Create metadata-only task chain
        tasks = RecordingTaskFactory.create_metadata_only_chain(
            stream_id=stream_id,
            recording_id=recording_id,
            mp4_file_path=mp4_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at
        )
        
        # Add tasks to dependency manager
        task_ids = []
        for task in tasks:
            await self.dependency_manager.add_task(task)
            task_ids.append(task.id)
            
        logger.info(f"Enqueued metadata generation for stream {stream_id} with {len(tasks)} tasks")
        
        return task_ids

    async def enqueue_thumbnail_generation(
        self,
        stream_id: int,
        recording_id: int,
        mp4_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str
    ) -> str:
        """Enqueue thumbnail generation task
        
        Returns:
            Task ID
        """
        # Create thumbnail task
        task = RecordingTaskFactory.create_thumbnail_only_task(
            stream_id=stream_id,
            recording_id=recording_id,
            mp4_file_path=mp4_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at
        )
        
        # Add to dependency manager
        await self.dependency_manager.add_task(task)
        
        logger.info(f"Enqueued thumbnail generation for stream {stream_id}")
        
        return task.id

    async def get_stream_task_status(self, stream_id: int) -> Dict[str, Any]:
        """Get the status of all tasks for a specific stream"""
        return self.dependency_manager.get_task_chain_info(stream_id)

    async def cancel_stream_tasks(self, stream_id: int) -> int:
        """Cancel all tasks for a specific stream
        
        Returns:
            Number of tasks cancelled
        """
        stream_tasks = [
            task for task in self.dependency_manager.tasks.values()
            if task.payload.get('stream_id') == stream_id
        ]
        
        cancelled_count = 0
        for task in stream_tasks:
            if task.status not in [DepTaskStatus.COMPLETED, DepTaskStatus.FAILED, DepTaskStatus.CANCELLED]:
                await self.dependency_manager.cancel_task(task.id)
                cancelled_count += 1
                
        logger.info(f"Cancelled {cancelled_count} tasks for stream {stream_id}")
        
        return cancelled_count

    async def _send_task_status_update(self, task: QueueTask):
        """Send task status update via WebSocket"""
        try:
            from app.dependencies import websocket_manager
            await websocket_manager.send_task_status_update(task.to_dict())
        except Exception as e:
            logger.debug(f"Failed to send task status update: {e}")

    async def _send_queue_stats_update(self):
        """Send queue statistics update via WebSocket"""
        try:
            from app.dependencies import websocket_manager
            stats = await self.get_stats()
            await websocket_manager.send_queue_stats_update(stats)
        except Exception as e:
            logger.debug(f"Failed to send queue stats update: {e}")

    async def _send_task_progress_update(self, task_id: str, progress: float, message: str = None):
        """Send task progress update via WebSocket"""
        try:
            from app.dependencies import websocket_manager
            await websocket_manager.send_task_progress_update(task_id, progress, message)
        except Exception as e:
            logger.debug(f"Failed to send task progress update: {e}")

    async def _process_task(self, task: QueueTask, worker_name: str):
        """Process a single task - enhanced with dependency manager integration"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        self.active_tasks[task.id] = task
        
        # Send WebSocket update for task start
        await self._send_task_status_update(task)
        
        log_with_context(
            logger, 'info',
            f"Processing task {task.task_type}",
            task_id=task.id,
            task_type=task.task_type,
            worker=worker_name,
            operation='task_start'
        )
        
        try:
            # Get task handler
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler registered for task type: {task.task_type}")
                
            # Execute the task
            await handler(task)
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100.0
            
            # Update dependency manager
            await self.dependency_manager.mark_task_completed(task.id)
            
            self.stats['completed_tasks'] += 1
            
            # Send WebSocket update for task completion
            await self._send_task_status_update(task)
            
            log_with_context(
                logger, 'info',
                f"Task {task.task_type} completed successfully",
                task_id=task.id,
                task_type=task.task_type,
                worker=worker_name,
                duration=(task.completed_at - task.started_at).total_seconds(),
                operation='task_complete'
            )
            
        except Exception as e:
            # Handle task failure
            task.error_message = str(e)
            task.retry_count += 1
            
            log_with_context(
                logger, 'error',
                f"Task {task.task_type} failed: {e}",
                task_id=task.id,
                task_type=task.task_type,
                worker=worker_name,
                error=str(e),
                retry_count=task.retry_count,
                operation='task_error'
            )
            
            # Mark as failed in dependency manager
            await self.dependency_manager.mark_task_failed(task.id, str(e))
            
            # For now, we don't retry dependency tasks here as they're managed by the dependency manager
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            self.stats['failed_tasks'] += 1
            
            # Send WebSocket update for task failure
            await self._send_task_status_update(task)
                
        finally:
            # Move task from active to completed
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
                
            # Store completed task (with size limit)
            self.completed_tasks[task.id] = task
            
            # Cleanup old completed tasks (keep last 1000)
            if len(self.completed_tasks) > 1000:
                oldest_tasks = sorted(
                    self.completed_tasks.items(),
                    key=lambda x: x[1].completed_at or datetime.min.replace(tzinfo=timezone.utc)
                )
                for task_id, _ in oldest_tasks[:100]:  # Remove oldest 100
                    del self.completed_tasks[task_id]

# Global instance
background_queue_service = BackgroundQueueService(max_workers=3)
