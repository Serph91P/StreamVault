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
from collections import defaultdict
from pathlib import Path
from .task_progress_tracker import QueueTask, TaskStatus, TaskPriority, TaskProgressTracker
from .worker_manager import WorkerManager
from app.services.processing.task_dependency_manager import TaskDependencyManager, Task, TaskStatus as DepTaskStatus

logger = logging.getLogger("streamvault")

# Configuration constants
DEFAULT_MAX_RETRIES = 3


class TaskQueueManager:
    """Core queue management and task orchestration with production concurrency fixes"""
    
    # Constants
    DEFAULT_STREAMER_NAME_FORMAT = "streamer_{stream_id}"
    
    def __init__(self, max_workers: int = 3, websocket_manager=None, enable_streamer_isolation: bool = True):
        self.enable_streamer_isolation = enable_streamer_isolation
        
        if enable_streamer_isolation:
            # Production fix: Use streamer-isolated queues to prevent concurrency issues
            self.streamer_queues: Dict[str, asyncio.PriorityQueue] = defaultdict(lambda: asyncio.PriorityQueue())
            self.streamer_workers: Dict[str, list] = defaultdict(list)
            self.max_workers_per_streamer = 4  # Increased: Allow 4 workers per streamer for better concurrency
            self.global_max_streamers = 15  # Increased: Support more concurrent streamers
            logger.info("TaskQueueManager initialized with streamer isolation for production - max 4 workers per streamer, 15 max streamers")
        else:
            # Original single shared queue
            self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
            logger.info("TaskQueueManager initialized with shared queue")
            
        self._is_running = False  # Use private attribute for internal state
        
        # Initialize components with queue manager reference
        self.progress_tracker = TaskProgressTracker(websocket_manager, queue_manager=self)
        self.worker_manager = WorkerManager(max_workers, self.progress_tracker, self.mark_task_completed)
        self.dependency_manager = TaskDependencyManager()
        
        # Dependency management
        self.dependency_worker: Optional[asyncio.Task] = None
        self.stats_worker: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """Get the current running status"""
        return self._is_running

    async def start(self):
        """Start the queue manager and all components"""
        if self._is_running:
            logger.debug("TaskQueueManager already running, skipping start...")
            return
            
        self._is_running = True
        
        if self.enable_streamer_isolation:
            # Start isolated workers per streamer (production fix)
            logger.info("Starting TaskQueueManager with streamer isolation")
            # Note: Individual streamer workers are created on-demand when tasks are enqueued
            # The dependency worker will handle task routing to appropriate streamer queues
        else:
            # Start shared worker manager (original)
            await self.worker_manager.start(self.task_queue)
        
        # Start dependency worker
        self.dependency_worker = asyncio.create_task(self._dependency_worker())
        
        # Start statistics broadcast worker
        self.stats_worker = asyncio.create_task(self._stats_broadcast_worker())
            
        logger.info("TaskQueueManager started with dependency management and stats broadcasting")

    async def stop(self):
        """Stop the queue manager and all components"""
        if not self._is_running:
            return
            
        self._is_running = False
        
        # Cancel dependency worker
        if self.dependency_worker:
            self.dependency_worker.cancel()
        
        # Cancel stats worker
        if self.stats_worker:
            self.stats_worker.cancel()
        
        if self.enable_streamer_isolation:
            # Stop all streamer workers
            stop_tasks = []
            for streamer_name, workers in self.streamer_workers.items():
                for worker in workers:
                    worker.cancel()
                    stop_tasks.append(worker)
            
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
                
            self.streamer_workers.clear()
            self.streamer_queues.clear()
        else:
            # Stop shared worker manager
            await self.worker_manager.stop()
        
        # Wait for dependency and stats workers to finish
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
        """Enqueue a new background task with optional streamer isolation"""
        
        # PRODUCTION FIX: Limit orphaned recovery check tasks to prevent queue flooding
        if task_type == 'orphaned_recovery_check':
            active_orphaned_count = sum(1 for task in self.progress_tracker.get_active_tasks().values() 
                                      if task.task_type == 'orphaned_recovery_check')
            
            if active_orphaned_count >= 3:  # Limit to max 3 concurrent orphaned checks
                logger.warning(f"🔍 ORPHANED_RECOVERY_LIMIT: Skipping new orphaned check - already {active_orphaned_count} running")
                # Return a dummy task ID but don't actually enqueue
                return f"skipped_orphaned_{uuid.uuid4()}"
        
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
        
        if self.enable_streamer_isolation:
            # Production fix: Route task to streamer-specific queue
            streamer_name = self._extract_streamer_name(payload)
            await self._enqueue_to_streamer_queue(task, streamer_name)
            logger.info(f"Enqueued task {task_id} ({task_type}) for streamer {streamer_name} with priority {priority.name}")
        else:
            # Original shared queue behavior
            priority_value = -priority.value
            await self.task_queue.put((priority_value, task))
            logger.info(f"Enqueued task {task_id} ({task_type}) with priority {priority.name}")
            
        return task_id

    def _extract_streamer_name(self, payload: Dict[str, Any]) -> str:
        """Extract streamer name from task payload for isolation"""
        # 1) Explicit name wins
        streamer_name = payload.get('streamer_name')
        if streamer_name:
            return str(streamer_name)

        # 2) Resolve by stream_id via DB (authoritative)
        stream_id = payload.get('stream_id')
        if stream_id is not None:
            try:
                # Lazy import to avoid circular deps
                from app.database import SessionLocal
                from app.models import Stream, Streamer
                with SessionLocal() as db:
                    stream = db.query(Stream).filter(Stream.id == int(stream_id)).first()
                    if stream:
                        st = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                        if st and st.username:
                            return str(st.username)
            except Exception as e:
                logger.debug(f"Streamer lookup by stream_id failed: {e}")

        # 3) Try to derive from provided paths (Windows-safe)
        def _candidate_from_path(path_str: str) -> Optional[str]:
            if not path_str:
                return None
            try:
                p = Path(path_str)
                # Heuristic: expect structure .../recordings/<streamer>/Season ...
                parts = list(p.parts)
                # Normalize typical top-level folder names
                lowered = [s.lower() for s in parts]
                if 'recordings' in lowered:
                    idx = lowered.index('recordings')
                    if idx + 1 < len(parts):
                        return str(parts[idx + 1])
                # Fallback: first non-empty folder name that isn't a drive or season
                for part in parts:
                    norm = part.strip().strip('\\/')
                    if not norm:
                        continue
                    # Skip drive letters like 'C:\'
                    if len(norm) == 2 and norm.endswith(':'):
                        continue
                    if norm.lower().startswith('season '):
                        continue
                    if norm.lower() in ('recordings', 'temp', 'tmp', 'segments'):
                        continue
                    return str(norm)
            except Exception:
                return None
            return None

        for key in ('ts_file_path', 'output_dir', 'mp4_path'):
            name = _candidate_from_path(payload.get(key, ''))
            if name:
                return name

        # 4) Fallbacks
        if stream_id is not None:
            return f"streamer_{stream_id}"
        return "unknown_streamer"

    async def _enqueue_to_streamer_queue(self, task: QueueTask, streamer_name: str):
        """Enqueue task to streamer-specific queue and ensure worker exists"""
        # Get or create streamer queue
        streamer_queue = self.streamer_queues[streamer_name]
        
        # Ensure worker exists for this streamer
        if streamer_name not in self.streamer_workers or not self.streamer_workers[streamer_name]:
            await self._create_streamer_worker(streamer_name, streamer_queue)
        
        # Enqueue task
        priority_value = -task.priority.value
        await streamer_queue.put((priority_value, task))

    async def _create_streamer_worker(self, streamer_name: str, streamer_queue: asyncio.PriorityQueue):
        """Create isolated worker for a specific streamer"""
        worker_name = f"streamer-{streamer_name}-worker"
        
        async def isolated_worker():
            """Isolated worker for a specific streamer"""
            logger.info(f"🎯 Started isolated worker for streamer: {streamer_name}")
            
            while self._is_running:
                try:
                    # Get next task from this streamer's queue
                    try:
                        priority, task = await asyncio.wait_for(
                            streamer_queue.get(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue
                    
                    logger.info(f"🔄 Streamer {streamer_name} worker processing task {task.id} ({task.task_type})")
                    
                    # Update task status to running
                    if self.progress_tracker:
                        self.progress_tracker.update_task_status(task.id, TaskStatus.RUNNING)
                    
                    try:
                        # Execute the task using worker manager's task execution logic
                        success = await self.worker_manager._execute_task(task, worker_name)
                        
                        # Mark task as completed
                        if self.progress_tracker:
                            status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
                            self.progress_tracker.update_task_status(task.id, status)
                            self.progress_tracker.update_task_progress(task.id, 100.0)
                        
                        # Notify completion callback
                        await self.mark_task_completed(task.id, success=success)
                        
                        logger.info(f"✅ Streamer {streamer_name} completed task {task.id} - success: {success}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error executing task {task.id} for streamer {streamer_name}: {e}", exc_info=True)
                        
                        # Mark task as failed
                        if self.progress_tracker:
                            self.progress_tracker.update_task_status(task.id, TaskStatus.FAILED)
                        
                        await self.mark_task_completed(task.id, success=False)
                        
                    finally:
                        # Always mark task as done in the queue to prevent hanging
                        streamer_queue.task_done()
                        
                except Exception as e:
                    logger.error(f"❌ Error in isolated worker for streamer {streamer_name}: {e}", exc_info=True)
                    await asyncio.sleep(1)
            
            logger.info(f"🛑 Stopped isolated worker for streamer: {streamer_name}")
        
        # Create and start the worker (limit to max_workers_per_streamer)
        current_worker_count = len(self.streamer_workers[streamer_name])
        if current_worker_count < self.max_workers_per_streamer:
            worker_task = asyncio.create_task(isolated_worker())
            self.streamer_workers[streamer_name].append(worker_task)
            logger.info(f"🎯 Created isolated worker for streamer: {streamer_name} (worker {current_worker_count + 1}/{self.max_workers_per_streamer})")
        else:
            logger.warning(f"⚠️ Maximum workers reached for streamer {streamer_name} ({self.max_workers_per_streamer})")

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
        
        while self._is_running:
            try:
                # Get ready tasks from dependency manager
                ready_tasks = await self.dependency_manager.get_ready_tasks()
                if ready_tasks:
                    logger.debug(
                        "🧩 DEP_WORKER_READY: count=%d tasks=%s",
                        len(ready_tasks),
                        ",".join([t.id for t in ready_tasks])
                    )
                for dep_task in ready_tasks:
                    # Skip tasks already completed in persistent state
                    try:
                        from app.database import SessionLocal
                        from app.models import RecordingProcessingState
                        with SessionLocal() as db:
                            rec_id = dep_task.payload.get('recording_id')
                            if rec_id:
                                state = db.query(RecordingProcessingState).filter(RecordingProcessingState.recording_id == rec_id).first()
                                if state:
                                    step = dep_task.type
                                    status_map = {
                                        'metadata_generation': state.metadata_status,
                                        'chapters_generation': state.chapters_status,
                                        'mp4_remux': state.mp4_remux_status,
                                        'mp4_validation': state.mp4_validation_status,
                                        'thumbnail_generation': state.thumbnail_status,
                                        'cleanup': state.cleanup_status,
                                    }
                                    if status_map.get(step) == 'completed':
                                        logger.info(f"⏭️ Skipping already-completed task {dep_task.id} ({step}) for recording {rec_id}")
                                        await self.dependency_manager.mark_task_completed(dep_task.id)
                                        continue
                    except Exception:
                        pass
                    # Find corresponding queue task
                    queue_task = self.progress_tracker.get_task(dep_task.id)
                    if queue_task:
                        # Mark dependency task as running
                        await self.dependency_manager.mark_task_running(dep_task.id)
                        
                        # Enqueue the actual task with proper routing
                        if self.enable_streamer_isolation:
                            streamer_name = self._extract_streamer_name(queue_task.payload)
                            await self._enqueue_to_streamer_queue(queue_task, streamer_name)
                        else:
                            priority_value = -queue_task.priority.value
                            await self.task_queue.put((priority_value, queue_task))
                        
                        logger.debug(f"Dependency worker enqueued ready task {dep_task.id}")
                
                # Brief pause before checking again - faster for multiple streams
                await asyncio.sleep(0.1)  # Reduced from 0.5s to 0.1s for better concurrency
                
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
        
        while self._is_running:
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
            # Diagnostic: find tasks that depend on this one and log their statuses
            dependents = [t.id for t in self.dependency_manager.tasks.values() if task_id in t.dependencies]
            if dependents:
                statuses = {}
                for d in dependents:
                    status = self.dependency_manager.get_task_status(d)
                    if status:
                        statuses[d] = status.value
                logger.info(
                    "🔗 TASK_COMPLETION_PROPAGATION: %s success=%s dependents=%s statuses=%s",
                    task_id,
                    success,
                    ",".join(dependents),
                    statuses
                )
            else:
                logger.info("🔗 TASK_COMPLETION_NO_DEPENDENTS: %s success=%s", task_id, success)
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
        
        if self.enable_streamer_isolation:
            # Streamer-isolated statistics
            streamer_stats = {}
            total_queue_size = 0
            total_workers = 0
            
            for streamer_name, queue in self.streamer_queues.items():
                queue_size = queue.qsize()
                worker_count = len(self.streamer_workers.get(streamer_name, []))
                
                streamer_stats[streamer_name] = {
                    'queue_size': queue_size,
                    'active_workers': worker_count,
                    'max_workers': self.max_workers_per_streamer
                }
                
                total_queue_size += queue_size
                total_workers += worker_count
            
            return {
                **base_stats,
                'queue_size': total_queue_size,
                'workers': {
                    'total': total_workers,
                    'max_per_streamer': self.max_workers_per_streamer,
                    'streamers': len(self.streamer_queues),
                    'isolation_enabled': True
                },
                'streamers': streamer_stats,
                'registered_handlers': self.worker_manager.get_registered_handlers()
            }
        else:
            # Original shared queue statistics
            worker_stats = self.worker_manager.get_worker_status()
            
            return {
                **base_stats,
                'queue_size': self.task_queue.qsize(),
                'workers': {
                    'total': self.worker_manager.max_workers,
                    'active': self.worker_manager.get_worker_count(),
                    'status': worker_stats,
                    'isolation_enabled': False
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
        # Persist created task IDs for the recording
        try:
            from app.database import SessionLocal
            from app.models import RecordingProcessingState
            with SessionLocal() as db:
                state = db.query(RecordingProcessingState).filter(RecordingProcessingState.recording_id == recording_id).first()
                if state:
                    state.set_task_ids({t.type: t.id for t in tasks})
                    db.commit()
        except Exception:
            pass
        
        # Add tasks to dependency manager and create corresponding queue tasks for tracking
        for task in tasks:
            await self.dependency_manager.add_task(task)

            # Create corresponding queue task for progress tracking and statistics
            # This is necessary because dependency manager uses different task objects
            # than the progress tracker requires for monitoring
            queue_task = self._create_queue_task_from_dependency_task(task)
            self.progress_tracker.add_task(queue_task)
        
        logger.info(f"Enqueued {len(tasks)} post-processing tasks for recording {recording_id}")
        
        # Return task IDs for tracking
        return [task.id for task in tasks]

    def _create_queue_task_from_dependency_task(self, task: Task) -> QueueTask:
        """Create a QueueTask from a dependency Task for progress tracking"""
        return QueueTask(
            id=task.id,
            task_type=task.type,
            priority=TaskPriority.NORMAL,
            payload=task.payload,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            max_retries=DEFAULT_MAX_RETRIES
        )
