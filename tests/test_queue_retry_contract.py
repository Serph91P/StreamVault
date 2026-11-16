"""#954: the production isolated and shared queues obey one retry contract."""

import asyncio
import time

import pytest

from app.services.queues.task_queue_manager import TaskQueueManager
from app.services.queues.task_progress_tracker import TaskStatus


async def terminal(manager, task_id):
    async with asyncio.timeout(12):
        while True:
            task = manager.get_task(task_id)
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return task
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [True, False])
@pytest.mark.parametrize("permanent", [True, False])
@pytest.mark.parametrize("budget", [1, 2])
async def test_exception_retry_budget_and_dependency_outcome(isolated, permanent, budget):
    manager = TaskQueueManager(max_workers=1, enable_streamer_isolation=isolated)
    attempts = []
    dependent_executed = asyncio.Event()

    async def parent(payload, progress=None):
        attempts.append(time.monotonic())
        if permanent or len(attempts) == 1:
            raise OSError("synthetic transient storage error")

    async def dependent(payload, progress=None):
        dependent_executed.set()

    manager.register_task_handler("parent", parent)
    manager.register_task_handler("dependent", dependent)
    await manager.start()
    try:
        parent_id = await manager.enqueue_task_with_dependencies(
            "parent", {"streamer_name": "synthetic"}, max_retries=budget
        )
        dependent_id = await manager.enqueue_task_with_dependencies(
            "dependent",
            {"streamer_name": "synthetic"},
            dependencies=[parent_id],
            max_retries=0,
        )
        parent_task = await terminal(manager, parent_id)
        expected_retries = budget if permanent else 1
        assert len(attempts) == expected_retries + 1
        for index in range(1, len(attempts)):
            assert attempts[index] - attempts[index - 1] >= 2**index
        assert parent_task.retry_count == expected_retries
        assert not manager.progress_tracker.progress_callbacks
        if permanent:
            assert parent_task.status is TaskStatus.FAILED
            assert "synthetic transient storage error" in parent_task.error_message
            assert not dependent_executed.is_set()
            assert (
                manager.dependency_manager.get_task_status(dependent_id).value
                == "failed"
            )
        else:
            assert parent_task.status is TaskStatus.COMPLETED
            await asyncio.wait_for(dependent_executed.wait(), 3)
            dependent_task = await terminal(manager, dependent_id)
            assert dependent_task.status is TaskStatus.COMPLETED
            assert (
                manager.dependency_manager.get_task_status(parent_id).value
                == "completed"
            )
    finally:
        await manager.stop()
