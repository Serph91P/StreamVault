"""Queue age cannot manufacture capture completion (#961)."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import sys
from types import SimpleNamespace

import pytest

from app.services.automatic_queue_recovery_service import AutomaticQueueRecoveryService
from app.services.background_queue_cleanup_service import BackgroundQueueCleanupService
from app.services.background_queue_service import BackgroundQueueService
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_manager import RecordingManager
from app.services.recording.recording_lifecycle_manager import RecordingLifecycleManager
from app.services.queues.task_progress_tracker import TaskStatus


@asynccontextmanager
async def capture_queue(monkeypatch):
    monkeypatch.setattr(BackgroundQueueService, "_instance", None)
    monkeypatch.setattr(BackgroundQueueService, "_initialized", False)
    queue = BackgroundQueueService()
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import sys; sys.stdin.buffer.read()",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    lease = SimpleNamespace(valid=True)

    async def authorized(**identity):
        assert identity["channel_key"] == "synthetic-961"
        assert identity["generation"] == 3
        assert identity["process_pid"] == child.pid
        assert identity["process_group_id"] == child.pid
        assert identity["process_start_fingerprint"] == "synthetic-fingerprint"
        if not lease.valid:
            raise PermissionError("synthetic stale generation")

    process_manager = ProcessManager.__new__(ProcessManager)
    process_manager.lock = asyncio.Lock()
    process_manager.active_processes = {"stream_42": child}
    process_manager.long_stream_processes = {
        "stream_42": {
            "upstream_channel_key": "synthetic-961",
            "upstream_generation": 3,
            "upstream_process_pid": child.pid,
            "upstream_process_group_id": child.pid,
            "upstream_process_start_fingerprint": "synthetic-fingerprint",
        }
    }
    process_manager.upstream_coordinator = SimpleNamespace(
        assert_stop_authorized=authorized
    )
    manager = RecordingManager.__new__(RecordingManager)
    manager._service = SimpleNamespace(
        process_manager=process_manager,
        get_active_recording=lambda recording_id: (
            {
                "stream_id": 42,
                "streamer_id": 1,
                "status": "recording",
                "file_path": "/synthetic.ts",
            }
            if recording_id == 7
            else None
        ),
    )

    async def capture_checker(recording_id):
        assert recording_id == 7
        return child.returncode is None and lease.valid

    # Existing consumers must honor an injected authoritative health source.
    queue.capture_checker = capture_checker
    queue.add_external_task(
        "recording_7", "recording", {"recording_id": 7, "stream_id": 42}
    )
    task = queue.external_tasks["recording_7"]
    task.created_at = task.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    task.last_progress_update = None
    try:
        yield queue, task, child, lease, manager, process_manager
    finally:
        if child.returncode is None:
            child.kill()
        await child.wait()
        await queue.queue_manager.progress_tracker.cleanup_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["automatic", "cleanup"])
async def test_two_hour_live_capture_without_heartbeat_remains_running(
    monkeypatch, consumer
):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        if consumer == "automatic":
            result = await AutomaticQueueRecoveryService(
                queue
            )._perform_recovery_check()
            assert result["recovered"] == 0
        else:
            result = await BackgroundQueueCleanupService(
                queue
            ).cleanup_stuck_recording_tasks()
            assert result["cleaned"] == 0
        assert queue.external_tasks[task.id] is task
        assert task.status is TaskStatus.RUNNING
        assert task.completed_at is None
        assert child.returncode is None


@pytest.mark.asyncio
async def test_live_capture_rechecked_before_recovery_mutation(monkeypatch):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        assert not await AutomaticQueueRecoveryService(queue)._recover_stuck_task(
            task.id, task
        )
        assert task.status is TaskStatus.RUNNING
        assert queue.external_tasks[task.id] is task


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["dead", "stale_lease"])
@pytest.mark.parametrize("consumer", ["automatic", "cleanup"])
@pytest.mark.parametrize("fresh_heartbeat", [False, True])
async def test_unhealthy_capture_is_failed_never_completed_by_age(
    monkeypatch, state, consumer, fresh_heartbeat
):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        if state == "dead":
            child.kill()
            await child.wait()
        else:
            lease.valid = False
        if fresh_heartbeat:
            task.last_progress_update = datetime.now(timezone.utc)
        if consumer == "automatic":
            result = await AutomaticQueueRecoveryService(
                queue
            )._perform_recovery_check()
            assert result["recovered"] == 1
        else:
            result = await BackgroundQueueCleanupService(
                queue
            ).cleanup_stuck_recording_tasks()
            assert result["cleaned"] == 1
        assert task.status is TaskStatus.FAILED
        assert task.progress < 100
        if state == "stale_lease":
            assert child.returncode is None
            assert pm.active_processes["stream_42"] is child


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["healthy", "dead", "stale_lease"])
async def test_manager_health_resolves_recording_to_actual_stream_and_fence(
    monkeypatch, state
):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        if state == "dead":
            child.kill()
            await child.wait()
        elif state == "stale_lease":
            lease.valid = False
        assert await manager.is_capture_running(7) is (state == "healthy")
        assert not await manager.is_capture_running(999)


@pytest.mark.asyncio
async def test_monitor_emits_heartbeat_without_percentage_or_progress_result(
    monkeypatch,
):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        lifecycle = RecordingLifecycleManager(process_manager=pm, queue_service=queue)
        before = datetime.now(timezone.utc)
        # Recording ID7 differs from stream42; legacy percentage lookup returns None.
        assert await pm.get_recording_progress(7) is None
        original_percentage = task.progress
        await lifecycle._update_recording_progress(7)
        assert task.last_progress_update is not None
        assert task.last_progress_update >= before
        assert task.progress == original_percentage
        assert task.status is TaskStatus.RUNNING


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["generation", "replacement", "replacement_denied"])
async def test_capture_identity_transition_is_unknown_not_dead(monkeypatch, change):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        entered, release = asyncio.Event(), asyncio.Event()
        original = pm.upstream_coordinator.assert_stop_authorized

        async def paused_authorization(**identity):
            await original(**identity)
            entered.set()
            await release.wait()
            if change == "replacement_denied":
                raise PermissionError("original generation changed")

        pm.upstream_coordinator.assert_stop_authorized = paused_authorization
        checking = asyncio.create_task(manager.is_capture_running(7))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            if change == "generation":
                pm.long_stream_processes["stream_42"]["upstream_generation"] = 4
            else:
                pm.long_stream_processes["stream_42"] = dict(
                    pm.long_stream_processes["stream_42"]
                )
        finally:
            release.set()
        assert await checking is None
        assert child.returncode is None


@pytest.mark.asyncio
async def test_legacy_capture_without_upstream_lease_still_reports_live(monkeypatch):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        pm.long_stream_processes.clear()
        assert await manager.is_capture_running(7) is True


@pytest.mark.asyncio
async def test_startup_binds_real_recording_manager_health_checker(monkeypatch):
    import importlib

    background_queue_init = importlib.import_module(
        "app.services.init.background_queue_init"
    )
    startup_init = importlib.import_module("app.services.init.startup_init")

    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        initialized = []

        async def initialize(*, enable_streamer_isolation):
            assert queue.capture_checker.__self__ is manager
            assert await queue.recording_task_liveness("recording_7") is True
            initialized.append(enable_streamer_isolation)

        monkeypatch.setattr(
            background_queue_init,
            "background_queue_manager",
            SimpleNamespace(
                is_initialized=False,
                queue_service=queue,
            ),
        )
        monkeypatch.setattr(
            background_queue_init, "initialize_background_queue", initialize
        )
        monkeypatch.setattr(startup_init, "get_recording_manager", lambda: manager)
        await startup_init.initialize_background_queue_with_fixes()
        assert len(initialized) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["automatic", "cleanup"])
async def test_unknown_capture_authority_does_not_manufacture_completion(
    monkeypatch, consumer
):
    async with capture_queue(monkeypatch) as (queue, task, child, lease, manager, pm):
        queue.capture_checker = None
        if consumer == "automatic":
            await AutomaticQueueRecoveryService(queue)._perform_recovery_check()
        else:
            await BackgroundQueueCleanupService(queue).cleanup_stuck_recording_tasks()
        assert task.status is TaskStatus.RUNNING
        assert queue.external_tasks[task.id] is task
