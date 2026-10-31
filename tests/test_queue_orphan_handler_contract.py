"""#965: production registration must be executable by the actual queue worker."""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.queues.task_progress_tracker import (
    QueueTask,
    TaskPriority,
    TaskStatus,
)
from app.services.queues.worker_manager import WorkerManager
from app.services.recording.orphaned_recovery_tasks import (
    handle_orphaned_recovery_check,
)
from datetime import datetime, timezone


@pytest.fixture
def recovery_boundary(monkeypatch):
    from app.services.recording import orphaned_recovery_service

    statistics = AsyncMock(return_value={"total_orphaned": 0})
    monkeypatch.setattr(
        orphaned_recovery_service,
        "get_orphaned_recovery_service",
        AsyncMock(return_value=SimpleNamespace(get_orphaned_statistics=statistics)),
    )
    return statistics


@pytest.mark.asyncio
async def test_initialized_isolated_queue_executes_registered_orphan_scan(
    monkeypatch, recovery_boundary
):
    from app.services import background_queue_service as queue_module
    from app.services import automatic_queue_recovery_service as automatic
    from app.services.init.background_queue_init import BackgroundQueueManager

    monkeypatch.setattr(queue_module.BackgroundQueueService, "_instance", None)
    monkeypatch.setattr(queue_module.BackgroundQueueService, "_initialized", False)
    service = queue_module.BackgroundQueueService()
    initialization = BackgroundQueueManager()
    initialization.queue_service = service
    monkeypatch.setattr(
        automatic,
        "get_recovery_service",
        lambda: SimpleNamespace(start=AsyncMock(), stop=AsyncMock()),
    )
    try:
        await initialization.initialize()
        handlers = service.queue_manager.worker_manager.task_handlers
        assert set(handlers) == {
            "metadata_generation",
            "chapters_generation",
            "mp4_remux",
            "mp4_validation",
            "thumbnail_generation",
            "cleanup",
            "orphaned_recovery_check",
            "segment_concatenation",
            "unified_recovery",
        }
        task_id = await service.enqueue_task(
            "orphaned_recovery_check",
            {"streamer_name": "synthetic", "max_age_hours": 12},
            max_retries=0,
        )
        await asyncio.wait_for(
            service.queue_manager.streamer_queues["synthetic"].join(), 3
        )
        task = service.get_task(task_id)
        assert task is not None
        assert task.status is TaskStatus.COMPLETED
        assert task.error_message is None
        for handler in handlers.values():
            inspect.signature(handler).bind({}, lambda value: None)
            inspect.signature(handler).bind({})
        recovery_boundary.assert_awaited_once_with(max_age_hours=12)
        assert not service.queue_manager.progress_tracker.progress_callbacks
    finally:
        await initialization.shutdown()


@pytest.mark.asyncio
async def test_orphan_scan_remains_executable_without_progress_tracker(
    recovery_boundary,
):
    worker = WorkerManager()
    worker.register_task_handler(
        "orphaned_recovery_check", handle_orphaned_recovery_check
    )
    task = QueueTask(
        id="scan",
        task_type="orphaned_recovery_check",
        priority=TaskPriority.NORMAL,
        payload={"max_age_hours": 9},
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    assert await worker._execute_task(task, "test")
    recovery_boundary.assert_awaited_once_with(max_age_hours=9)
