"""
WorkerManager - Worker thread management and task execution

Extracted from background_queue_service.py God Class
Handles worker threads, task execution, and retry logic.
"""

import asyncio
import logging
import traceback
from typing import Dict, List, Callable, Optional
from .task_progress_tracker import QueueTask, TaskStatus, TaskProgressTracker
from app.config.constants import ASYNC_DELAYS

logger = logging.getLogger("streamvault")


class WorkerManager:
    """Manages worker threads and task execution"""

    def __init__(self, max_workers: int = 3, progress_tracker: Optional[TaskProgressTracker] = None, completion_callback: Optional[Callable] = None):
        """
        Initialize the WorkerManager.

        Args:
            max_workers (int): The maximum number of worker threads to run concurrently.
            progress_tracker (Optional[TaskProgressTracker]): An optional tracker for monitoring task progress.
            completion_callback (Optional[Callable]): An optional callback function executed when a task completes.
                The callback should have the signature `async def callback(task_id: str, success: bool) -> None`,
                where `task_id` is the ID of the completed task and `success` indicates whether
                the task completed successfully (True) or failed (False).
        """
        self.max_workers = max_workers
        self.progress_tracker = progress_tracker
        self.completion_callback = completion_callback
        self.workers: List[asyncio.Task] = []
        self.is_running = False
        self.task_handlers: Dict[str, Callable] = {}

    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a handler for a specific task type"""
        self.task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

    async def start(self, task_queue: asyncio.PriorityQueue):
        """Start worker threads"""
        if self.is_running:
            logger.warning("WorkerManager already running")
            return

        self.is_running = True
        self.task_queue = task_queue

        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

        logger.info(f"WorkerManager started with {self.max_workers} workers")

    async def stop(self):
        """Stop all worker threads"""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers.clear()
        logger.info("WorkerManager stopped")

    async def _worker(self, worker_name: str):
        """Worker coroutine that processes tasks from the queue"""
        logger.info(f"Worker {worker_name} started")

        while self.is_running:
            try:
                # Get next task from queue with timeout
                try:
                    priority, task = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                logger.debug(f"Worker {worker_name} processing task {task.id} ({task.task_type})")

                # Update task status to running
                if self.progress_tracker:
                    self.progress_tracker.update_task_status(task.id, TaskStatus.RUNNING)

                try:
                    # Execute the task
                    await self._execute_task(task, worker_name)

                    # Mark task as completed successfully
                    if self.progress_tracker:
                        self.progress_tracker.update_task_status(task.id, TaskStatus.COMPLETED)
                        self.progress_tracker.update_task_progress(task.id, 100.0)

                    # Notify completion callback (for dependency management)
                    if self.completion_callback:
                        await self.completion_callback(task.id, success=True)

                    logger.info(f"Worker {worker_name} completed task {task.id} - success: True")

                except Exception as e:
                    error_msg = f"Task execution failed: {str(e)}"
                    logger.error(f"Worker {worker_name} task {task.id} failed: {error_msg}")
                    logger.error(traceback.format_exc())

                    # Handle task failure and potential retry
                    await self._handle_task_failure(task, error_msg, worker_name)

                    # Notify completion callback about failure
                    if self.completion_callback:
                        await self.completion_callback(task.id, success=False)

                finally:
                    # Mark task as done in the queue
                    self.task_queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} unexpected error: {e}")
                await asyncio.sleep(ASYNC_DELAYS.WORKER_SHUTDOWN_PAUSE)

        logger.info(f"Worker {worker_name} stopped")

    async def _execute_task(self, task: QueueTask, worker_name: str) -> bool:
        """Execute a single task and return success status"""
        task_type = task.task_type

        if task_type not in self.task_handlers:
            raise ValueError(f"No handler registered for task type: {task_type}")

        handler = self.task_handlers[task_type]

        # Create progress callback if tracker is available
        progress_callback = None
        if self.progress_tracker:
            def update_progress(progress: float):
                self.progress_tracker.update_task_progress(task.id, progress)
            progress_callback = update_progress
            self.progress_tracker.register_progress_callback(task.id, progress_callback)

        try:
            # Execute the handler
            if asyncio.iscoroutinefunction(handler):
                # Async handler
                if progress_callback:
                    await handler(task.payload, progress_callback)
                else:
                    await handler(task.payload)
            else:
                # Sync handler - run in thread pool
                if progress_callback:
                    await asyncio.get_event_loop().run_in_executor(
                        None, handler, task.payload, progress_callback
                    )
                else:
                    await asyncio.get_event_loop().run_in_executor(
                        None, handler, task.payload
                    )

            # If we reach here, the task executed successfully
            return True

        except Exception as e:
            # Task execution failed - log and re-raise for proper error handling
            logger.error(f"Exception occurred while executing task {task.id}: {e}")
            raise

        finally:
            # Clean up progress callback
            if self.progress_tracker and progress_callback:
                self.progress_tracker.unregister_progress_callback(task.id)

    async def _handle_task_failure(self, task: QueueTask, error_msg: str, worker_name: str):
        """Handle task failure and retry logic"""
        if task.retry_count < task.max_retries:
            # Retry the task
            task.retry_count += 1

            if self.progress_tracker:
                self.progress_tracker.update_task_status(task.id, TaskStatus.RETRYING)

            # Calculate retry delay (exponential backoff)
            retry_delay = min(2 ** task.retry_count, 60)  # Max 60 seconds

            logger.info(f"Worker {worker_name} retrying task {task.id} in {retry_delay}s "
                        f"(attempt {task.retry_count + 1}/{task.max_retries + 1})")

            # Re-queue the task after delay
            await asyncio.sleep(retry_delay)
            priority = task.priority.value
            await self.task_queue.put((priority, task))

        else:
            # Max retries exceeded, mark as failed
            if self.progress_tracker:
                self.progress_tracker.update_task_status(task.id, TaskStatus.FAILED, error_msg)

            logger.error(f"Worker {worker_name} task {task.id} failed permanently after "
                         f"{task.max_retries} retries: {error_msg}")

    def get_worker_count(self) -> int:
        """Get number of active workers"""
        return len([w for w in self.workers if not w.done()])

    def get_worker_status(self) -> Dict[str, bool]:
        """Get status of all workers"""
        status = {}
        for i, worker in enumerate(self.workers):
            worker_name = f"worker-{i}"
            status[worker_name] = not worker.done()
        return status

    async def wait_for_completion(self, timeout: Optional[float] = None):
        """Wait for all current tasks to complete"""
        if hasattr(self, 'task_queue'):
            try:
                await asyncio.wait_for(self.task_queue.join(), timeout=timeout)
                logger.info("All tasks completed")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for task completion after {timeout}s")

    def get_registered_handlers(self) -> List[str]:
        """Get list of registered task types"""
        return list(self.task_handlers.keys())

    def has_handler(self, task_type: str) -> bool:
        """Check if handler is registered for task type"""
        return task_type in self.task_handlers

    def unregister_handler(self, task_type: str) -> bool:
        """Unregister a task handler"""
        if task_type in self.task_handlers:
            del self.task_handlers[task_type]
            logger.info(f"Unregistered handler for task type: {task_type}")
            return True
        return False

    def clear_handlers(self):
        """Clear all registered handlers"""
        self.task_handlers.clear()
        logger.info("All task handlers cleared")
