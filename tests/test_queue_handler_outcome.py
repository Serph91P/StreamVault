"""#955 original eea67f69: negative returns must not release dependents."""

import asyncio
from datetime import datetime, timezone

import pytest

from app.services.queues.task_queue_manager import TaskQueueManager
from app.services.queues.task_progress_tracker import (
    QueueTask,
    TaskPriority,
    TaskStatus,
)
from app.services.queues.worker_manager import WorkerManager
from app.services.recording.segment_concatenation_task import (
    handle_segment_concatenation,
)
from test_queue_retry_contract import terminal


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [True, False])
@pytest.mark.parametrize("synchronous", [True, False])
@pytest.mark.parametrize(
    "failure", [False, {"success": False, "error": "synthetic missing input"}]
)
async def test_negative_return_retries_and_never_releases_dependents(
    isolated, synchronous, failure
):
    manager = TaskQueueManager(max_workers=1, enable_streamer_isolation=isolated)
    attempts = []
    dependent_called = asyncio.Event()

    def sync_handler(payload, progress=None):
        attempts.append(1)
        return failure

    async def async_handler(payload, progress=None):
        return sync_handler(payload, progress)

    async def dependent(payload, progress=None):
        dependent_called.set()

    manager.register_task_handler(
        "negative", sync_handler if synchronous else async_handler
    )
    manager.register_task_handler("dependent", dependent)
    await manager.start()
    try:
        task_id = await manager.enqueue_task_with_dependencies(
            "negative", {"streamer_name": "synthetic"}, max_retries=1
        )
        dependent_id = await manager.enqueue_task_with_dependencies(
            "dependent",
            {"streamer_name": "synthetic"},
            dependencies=[task_id],
            max_retries=0,
        )
        task = await terminal(manager, task_id)
        assert task.status is TaskStatus.FAILED
        assert len(attempts) == 2
        assert task.retry_count == 1
        assert task.error_message
        if isinstance(failure, dict):
            assert failure["error"] in task.error_message
        assert (
            manager.dependency_manager.get_task_status(dependent_id).value == "failed"
        )
        assert not dependent_called.is_set()
        assert not manager.progress_tracker.progress_callbacks
    finally:
        await manager.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [True, False])
async def test_real_segment_handler_missing_input_is_terminal_failure_without_fs_changes(
    isolated, tmp_path
):
    segment = tmp_path / "capture.ts"
    segment.write_bytes(b"synthetic original")
    output = tmp_path / "final.ts"
    manager = TaskQueueManager(enable_streamer_isolation=isolated)
    manager.register_task_handler("segment_concatenation", handle_segment_concatenation)
    await manager.start()
    try:
        task_id = await manager.enqueue_task(
            "segment_concatenation",
            {
                "streamer_name": "synthetic",
                "segment_files": [str(segment)],
                "output_path": str(output),
            },
            max_retries=0,
        )
        task = await terminal(manager, task_id)
        assert task.status is TaskStatus.FAILED
        assert "Missing required parameters" in task.error_message
        assert segment.read_bytes() == b"synthetic original"
        assert not output.exists()
    finally:
        await manager.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("synchronous", [True, False])
async def test_negative_return_without_tracker_uses_same_failure_contract(synchronous):
    def sync_handler(payload):
        return {"success": False, "error": "synthetic no-tracker failure"}

    async def async_handler(payload):
        return sync_handler(payload)

    manager = WorkerManager()
    manager.register_task_handler(
        "negative", sync_handler if synchronous else async_handler
    )
    task = QueueTask(
        id="synthetic",
        task_type="negative",
        priority=TaskPriority.NORMAL,
        payload={},
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(RuntimeError, match="synthetic no-tracker failure"):
        await manager._execute_task(task, "test")


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [None, True, {"success": True}, {"skipped": True}])
@pytest.mark.parametrize("synchronous", [True, False])
async def test_legacy_positive_and_no_result_handlers_remain_successful(
    result, synchronous
):
    manager = TaskQueueManager()

    def sync_handler(payload, progress=None):
        return result

    async def async_handler(payload, progress=None):
        return result

    manager.register_task_handler(
        "positive", sync_handler if synchronous else async_handler
    )
    await manager.start()
    try:
        task_id = await manager.enqueue_task(
            "positive", {"streamer_name": "synthetic"}, max_retries=0
        )
        task = await terminal(manager, task_id)
        assert task.status is TaskStatus.COMPLETED
        assert task.retry_count == 0
        assert task.error_message is None
    finally:
        await manager.stop()
