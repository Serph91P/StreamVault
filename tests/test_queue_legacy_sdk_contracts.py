"""Retained in-memory SDK commands; no durable/media/provider execution claim."""

import importlib
from datetime import datetime, timezone

import pytest

from app.services.background_queue_service import BackgroundQueueService
from app.services.communication.websocket_manager import ConnectionManager
from app.services.init.background_queue_init import BackgroundQueueManager
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)
from app.services.queues.task_progress_tracker import TaskStatus


@pytest.fixture
async def legacy_queue(monkeypatch):
    module = importlib.import_module("app.services.init.background_queue_init")
    socket = ConnectionManager()
    queue = BackgroundQueueService.for_application(socket)
    handlers = PostProcessingTaskHandlers(connection_manager=socket)
    manager = BackgroundQueueManager(queue_service=queue, task_handlers=handlers)
    monkeypatch.setattr(module, "background_queue_manager", manager)
    try:
        yield module, queue
    finally:
        await queue.stop()
        await handlers.cleanup()


@pytest.mark.asyncio
async def test_sdk_metadata_thumbnail_status_and_stream_cancellation_preserve_other_streams(
    legacy_queue, tmp_path
):
    module, queue = legacy_queue
    media = tmp_path / "existing.mp4"
    media.write_bytes(b"storage marker, not a decoder fixture")
    args = dict(
        stream_id=42,
        recording_id=7,
        mp4_file_path=str(media),
        output_dir=str(tmp_path),
        streamer_name="legacy",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    ids = await module.enqueue_metadata_generation(**args)
    thumbnail = await module.enqueue_thumbnail_generation(**args)
    assert len(ids) == 3 and thumbnail not in ids
    assert {queue.active_tasks[identifier].task_type for identifier in ids} == {
        "metadata_generation",
        "chapters_generation",
        "thumbnail_generation",
    }
    assert all(
        queue.active_tasks[identifier].payload["recording_id"] == 7
        for identifier in [*ids, thumbnail]
    )
    other = await module.enqueue_thumbnail_generation(
        **{**args, "stream_id": 43, "recording_id": 8}
    )
    queue.add_external_task("capture-42", "recording", {"stream_id": 42})
    queue.add_external_task("capture-43", "recording", {"stream_id": 43})
    await queue.queue_manager.mark_task_completed(ids[0], success=True)
    # Seed the SDK's terminal tracking state separately from dependency state;
    # these compatibility commands are not a media execution/worker test.
    queue.queue_manager.progress_tracker.update_task_status(
        ids[0], TaskStatus.COMPLETED
    )
    before = await module.get_stream_task_status(42)
    assert {row["id"] for row in before["active"]} == {*ids[1:], thumbnail}
    assert {row["id"] for row in before["completed"]} == {ids[0]}
    assert {row["id"] for row in before["external"]} == {"capture-42"}
    result = await module.cancel_stream_tasks(42)
    assert result == {"success": True, "cancelled_count": 4, "stream_id": 42}
    assert queue.external_tasks["capture-42"].status is TaskStatus.FAILED
    assert queue.external_tasks["capture-43"].status is TaskStatus.RUNNING
    assert queue.active_tasks[other].status is TaskStatus.PENDING
    assert media.read_bytes() == b"storage marker, not a decoder fixture"
    assert all(
        queue.dependency_manager.get_task_status(identifier).value == "failed"
        for identifier in [*ids[1:], thumbnail]
    )
    assert queue.dependency_manager.get_task_status(other).value == "ready"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["metadata", "thumbnail"])
async def test_sdk_rejects_failed_dependency_admission_without_publishing_task_success(
    legacy_queue, tmp_path, monkeypatch, kind
):
    module, queue = legacy_queue

    async def denied(_task):
        raise PermissionError("synthetic SDK dependency admission denied")

    monkeypatch.setattr(queue.dependency_manager, "add_task", denied)
    command = (
        module.enqueue_metadata_generation
        if kind == "metadata"
        else module.enqueue_thumbnail_generation
    )
    with pytest.raises(
        PermissionError, match="synthetic SDK dependency admission denied"
    ):
        await command(
            42,
            7,
            str(tmp_path / "existing.mp4"),
            str(tmp_path),
            "legacy",
            "2026-01-01T00:00:00",
        )
    assert queue.active_tasks == {} and queue.completed_tasks == {}


@pytest.mark.asyncio
async def test_sdk_initialize_shutdown_are_idempotent_in_supported_shared_queue_mode(
    legacy_queue,
):
    module, queue = legacy_queue
    await module.initialize_background_queue(enable_streamer_isolation=False)
    workers = list(queue.queue_manager.worker_manager.workers)
    assert workers and queue.is_running
    await module.initialize_background_queue(enable_streamer_isolation=False)
    assert queue.queue_manager.worker_manager.workers == workers
    await module.shutdown_background_queue()
    assert all(worker.done() for worker in workers)
    assert not queue.is_running and not module.background_queue_manager.is_initialized
    await module.shutdown_background_queue()


@pytest.mark.asyncio
async def test_orphan_callback_preserves_real_concurrency_limit_without_resolving_default_recovery(
    legacy_queue,
):
    from app.services.recording.orphaned_recovery_tasks import (
        handle_orphaned_recovery_check,
    )

    _, queue = legacy_queue
    ids = [f"held-orphan-{index}" for index in range(4)]
    for identifier in ids:
        queue.add_external_task(
            identifier, "orphaned_recovery_check", {"streamer_name": "held"}
        )
    result = await handle_orphaned_recovery_check({}, queue_service=queue)
    assert result == {
        "success": True,
        "orphaned_found": 0,
        "recovery_triggered": 0,
        "message": "Skipped - too many orphaned checks running (4)",
    }
    assert set(queue.get_active_tasks()) == set(ids)
    assert all(
        task.status is TaskStatus.RUNNING for task in queue.get_active_tasks().values()
    )


@pytest.mark.asyncio
async def test_orphan_callback_returns_structured_failure_for_unavailable_recovery_owner(
    legacy_queue, monkeypatch
):
    from app.services.recording.orphaned_recovery_tasks import (
        handle_orphaned_recovery_check,
    )

    _, queue = legacy_queue

    async def unavailable():
        raise RuntimeError("synthetic-recovery-owner-unavailable")

    monkeypatch.setattr(
        importlib.import_module("app.services.recording.orphaned_recovery_service"),
        "get_orphaned_recovery_service",
        unavailable,
    )
    result = await handle_orphaned_recovery_check({}, queue_service=queue)
    assert result["success"] is False
    assert result["error"] == "synthetic-recovery-owner-unavailable"
    assert result["message"].startswith("Orphaned recovery check failed:")
    assert queue.active_tasks == {} and queue.completed_tasks == {}
