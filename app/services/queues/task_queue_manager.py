"""
TaskQueueManager - Core queue management and task orchestration

Extracted from background_queue_service.py God Class
Handles task enqueueing, dependency management, and queue coordination.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from .task_progress_tracker import QueueTask, TaskStatus, TaskPriority, TaskProgressTracker
from .worker_manager import WorkerManager
from app.services.processing.task_dependency_manager import TaskDependencyManager, Task, TaskStatus as DepTaskStatus

logger = logging.getLogger("streamvault")


class TaskQueueManager:
    """Core queue management and task orchestration"""
    
    # Constants
    DEFAULT_STREAMER_NAME_FORMAT = "streamer_{stream_id}"
    
    def __init__(self, max_workers: int = 3, websocket_manager=None):
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.is_running = False
        
        # Initialize components
        self.progress_tracker = TaskProgressTracker(websocket_manager)
        self.worker_manager = WorkerManager(max_workers, self.progress_tracker, self.mark_task_completed)
        self.dependency_manager = TaskDependencyManager()
        
        # Dependency management
        self.dependency_worker: Optional[asyncio.Task] = None
        self.stats_worker: Optional[asyncio.Task] = None

    async def start(self):
        """Start the queue manager and all components"""
        if self.is_running:
            logger.debug("TaskQueueManager already running, skipping start...")
            return
            
        self.is_running = True
        
        # Start worker manager
        await self.worker_manager.start(self.task_queue)
        
        # Start dependency worker
        self.dependency_worker = asyncio.create_task(self._dependency_worker())
        
        # Start statistics broadcast worker
        self.stats_worker = asyncio.create_task(self._stats_broadcast_worker())
            
        logger.info("TaskQueueManager started with dependency management and stats broadcasting")

    async def stop(self):
        """Stop the queue manager and all components"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # Cancel dependency worker
        if self.dependency_worker:
            self.dependency_worker.cancel()
        
        # Cancel stats worker
        if self.stats_worker:
            self.stats_worker.cancel()
        
        # Stop worker manager
        await self.worker_manager.stop()
        
        # Wait for workers to finish
        workers_to_wait = []
        if self.dependency_worker:
            workers_to_wait.append(self.dependency_worker)
        if self.stats_worker:
            workers_to_wait.append(self.stats_worker)
            
        if workers_to_wait:
            await asyncio.gather(*workers_to_wait, return_exceptions=True)
            
        self.dependency_worker = None
        self.stats_worker = None
        
        # Shutdown dependency manager
        await self.dependency_manager.shutdown()
        
        logger.info("TaskQueueManager stopped")

    def register_task_handler(self, task_type: str, handler):
        """Register a handler for a specific task type"""
        self.worker_manager.register_task_handler(task_type, handler)

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
        
        # Add to progress tracker
        self.progress_tracker.add_task(task)
        
        # Put task in queue (priority queue uses negative value for higher priority)
        priority_value = -priority.value
        await self.task_queue.put((priority_value, task))
        
        logger.info(f"Enqueued task {task_id} ({task_type}) with priority {priority.name}")
        return task_id

    async def enqueue_task_with_dependencies(
        self,
        task_type: str,
        payload: Dict[str, Any],
        dependencies: Optional[list] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3
    ) -> str:
        """Enqueue a task with dependencies"""
        task_id = str(uuid.uuid4())
        
        # Create dependency task
        dep_task = Task(
            id=task_id,
            type=task_type,
            payload=payload,
            dependencies=set(dependencies or []),
            status=DepTaskStatus.PENDING
        )
        
        # Add to dependency manager
        await self.dependency_manager.add_task(dep_task)
        
        # Create queue task but don't enqueue yet (dependency manager will handle it)
        queue_task = QueueTask(
            id=task_id,
            task_type=task_type,
            priority=priority,
            payload=payload,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            max_retries=max_retries
        )
        
        # Add to progress tracker
        self.progress_tracker.add_task(queue_task)
        
        logger.info(f"Enqueued task {task_id} ({task_type}) with {len(dependencies or [])} dependencies")
        return task_id

    async def _dependency_worker(self):
        """Worker that manages task dependencies"""
        logger.info("Dependency worker started")
        
        while self.is_running:
            try:
                # Get ready tasks from dependency manager
                ready_tasks = await self.dependency_manager.get_ready_tasks()
                
                for dep_task in ready_tasks:
                    # Find corresponding queue task
                    queue_task = self.progress_tracker.get_task(dep_task.id)
                    if queue_task:
                        # Mark dependency task as running
                        await self.dependency_manager.mark_task_running(dep_task.id)
                        
                        # Enqueue the actual task
                        priority_value = -queue_task.priority.value
                        await self.task_queue.put((priority_value, queue_task))
                        
                        logger.debug(f"Dependency worker enqueued ready task {dep_task.id}")
                
                # Brief pause before checking again
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                logger.info("Dependency worker cancelled")
                break
            except Exception as e:
                logger.error(f"Dependency worker error: {e}")
                await asyncio.sleep(1)
                
        logger.info("Dependency worker stopped")

    async def _stats_broadcast_worker(self):
        """Worker that periodically broadcasts queue statistics"""
        logger.info("Stats broadcast worker started")
        
        while self.is_running:
            try:
                # Send queue statistics via WebSocket
                await self.progress_tracker.send_queue_statistics()
                
                # Wait 10 seconds before next broadcast
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                logger.info("Stats broadcast worker cancelled")
                break
            except Exception as e:
                logger.warning(f"Stats broadcast worker error: {e}")
                await asyncio.sleep(5)  # Wait shorter on error
                
        logger.info("Stats broadcast worker stopped")

    async def mark_task_completed(self, task_id: str, success: bool = True):
        """Mark a task as completed in dependency manager"""
        try:
            if success:
                await self.dependency_manager.mark_task_completed(task_id)
            else:
                await self.dependency_manager.mark_task_failed(task_id, "Task execution failed")
            logger.debug(f"Task {task_id} marked as {'completed' if success else 'failed'} in dependency manager")
        except Exception as e:
            logger.warning(f"Failed to update task {task_id} in dependency manager: {e}")

    # Progress and status methods (delegate to progress tracker)
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status"""
        return self.progress_tracker.get_task_status(task_id)

    def get_task_progress(self, task_id: str) -> Optional[float]:
        """Get task progress"""
        return self.progress_tracker.get_task_progress(task_id)

    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """Get task by ID"""
        return self.progress_tracker.get_task(task_id)

    def get_active_tasks(self) -> Dict[str, QueueTask]:
        """Get all active tasks"""
        return self.progress_tracker.get_active_tasks()

    def get_completed_tasks(self) -> Dict[str, QueueTask]:
        """Get all completed tasks"""
        return self.progress_tracker.get_completed_tasks()

    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        base_stats = self.progress_tracker.get_statistics()
        worker_stats = self.worker_manager.get_worker_status()
        
        return {
            **base_stats,
            'queue_size': self.task_queue.qsize(),
            'workers': {
                'total': self.worker_manager.max_workers,
                'active': self.worker_manager.get_worker_count(),
                'status': worker_stats
            },
            'registered_handlers': self.worker_manager.get_registered_handlers()
        }

    async def send_queue_statistics(self):
        """Send queue statistics via WebSocket"""
        await self.progress_tracker.send_queue_statistics()

    # External task tracking (delegate to progress tracker)
    
    def add_external_task(self, task_id: str, task_type: str, payload: Dict[str, Any]):
        """Add an external task for tracking"""
        self.progress_tracker.add_external_task(task_id, task_type, payload)

    def update_external_task_progress(self, task_id: str, progress: float):
        """Update external task progress"""
        self.progress_tracker.update_external_task_progress(task_id, progress)

    def complete_external_task(self, task_id: str, success: bool = True):
        """Mark external task as completed"""
        self.progress_tracker.complete_external_task(task_id, success)

    def remove_external_task(self, task_id: str):
        """Remove external task from tracking"""
        self.progress_tracker.remove_external_task(task_id)

    # Utility methods
    
    async def wait_for_completion(self, timeout: Optional[float] = None):
        """Wait for all current tasks to complete"""
        await self.worker_manager.wait_for_completion(timeout)

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        self.progress_tracker.cleanup_old_tasks(max_age_hours)

    def clear_all_tasks(self):
        """Clear all tasks (for shutdown)"""
        self.progress_tracker.clear_all_tasks()

    def get_registered_handlers(self) -> list:
        """Get list of registered task types"""
        return self.worker_manager.get_registered_handlers()

    def has_handler(self, task_type: str) -> bool:
        """Check if handler is registered for task type"""
        return self.worker_manager.has_handler(task_type)
    
    async def enqueue_recording_post_processing(self, *args, **kwargs):
        """Enqueue a complete post-processing chain for a recording"""
        from app.services.processing.recording_task_factory import RecordingTaskFactory
        
        # Handle single payload argument (from coordinator)
        if len(args) == 1 and isinstance(args[0], dict):
            payload = args[0]
            stream_id = payload.get('stream_id')
            recording_id = payload.get('recording_id')
            ts_file_path = payload.get('ts_file_path')
            output_dir = payload.get('output_dir')
            streamer_name = payload.get('streamer_name')
            started_at = payload.get('started_at')
            cleanup_ts_file = payload.get('cleanup_ts_file', True)
        else:
            # Extract parameters from kwargs
            stream_id = kwargs.get('stream_id')
            recording_id = kwargs.get('recording_id')
            ts_file_path = kwargs.get('ts_file_path')
            output_dir = kwargs.get('output_dir')
            streamer_name = kwargs.get('streamer_name')
            started_at = kwargs.get('started_at')
            cleanup_ts_file = kwargs.get('cleanup_ts_file', True)
        
        # Type conversion and validation
        if stream_id is not None and not isinstance(stream_id, int):
            try:
                stream_id = int(stream_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid stream_id: {stream_id}")
                raise ValueError(f"Invalid stream_id: {stream_id}")
        
        if recording_id is not None and not isinstance(recording_id, int):
            try:
                recording_id = int(recording_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid recording_id: {recording_id}")
                raise ValueError(f"Invalid recording_id: {recording_id}")
        
        # For missing values, try to derive them or use defaults
        if not output_dir and ts_file_path:
            from pathlib import Path
            output_dir = str(Path(ts_file_path).parent)
        
        if not streamer_name:
            streamer_name = self.DEFAULT_STREAMER_NAME_FORMAT.format(stream_id=stream_id)
        
        if not started_at:
            from datetime import datetime
            started_at = datetime.now().isoformat()
        
        # Final validation
        if not all([stream_id is not None, recording_id is not None, ts_file_path, output_dir, streamer_name, started_at]):
            logger.error(f"Missing required parameters for post-processing: stream_id={stream_id}, recording_id={recording_id}, ts_file_path={ts_file_path}, output_dir={output_dir}, streamer_name={streamer_name}, started_at={started_at}")
            raise ValueError("Missing required parameters for post-processing")
        
        # Ensure all parameters are correctly typed after validation
        if stream_id is None or recording_id is None:
            raise ValueError("stream_id and recording_id must not be None")
        if not all([ts_file_path, output_dir, streamer_name, started_at]):
            raise ValueError("ts_file_path, output_dir, streamer_name, and started_at must not be empty or None")
        
        # Create task factory and generate tasks
        task_factory = RecordingTaskFactory()
        tasks = task_factory.create_post_processing_chain(
            stream_id=stream_id,
            recording_id=recording_id,
            ts_file_path=ts_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at,
            cleanup_ts_file=cleanup_ts_file
        )
        
        # Add tasks to dependency manager
        for task in tasks:
            await self.dependency_manager.add_task(task)
        
        logger.info(f"Enqueued {len(tasks)} post-processing tasks for recording {recording_id}")
        
        # Return task IDs for tracking
        return [task.id for task in tasks]
