"""Durable admission bounds must defer work, not lose accepted job identities."""

import asyncio

import pytest
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

from app.database import Base
from app.services.queues.task_progress_tracker import TaskStatus
from app.services.queues.task_queue_manager import TaskQueueManager

catalog_sessions = _catalog_sessions


def test_production_facade_uses_durable_admission():
    from app.services.background_queue_service import background_queue_service
    from app.services.queues.durable_task_store import DurableTaskStore

    assert isinstance(
        background_queue_service.queue_manager.task_store, DurableTaskStore
    )


async def eventually(predicate, timeout=10):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize(
    "heavy_type",
    [
        "mp4_remux",
        "metadata_generation",
        "mp4_validation",
        "unified_recovery",
        "orphaned_recovery_check",
    ],
)
async def test_durable_backlog_light_work_and_stop_restart(
    catalog_sessions, tmp_path, monkeypatch, isolated, heavy_type
):
    from app.services.queues.durable_task_store import DurableTaskStore

    from app.config.settings import get_settings

    sessions, _ = catalog_sessions
    engine = sessions.kw["bind"]
    monkeypatch.setattr(get_settings(), "RECORDING_DIRECTORY", str(tmp_path))
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    store = DurableTaskStore(sessions)
    queue = TaskQueueManager(
        max_workers=3, enable_streamer_isolation=isolated, task_store=store
    )
    release = asyncio.Event()
    started = []
    effects = []
    light = asyncio.Event()

    async def heavy(payload, progress):
        started.append(payload["n"])
        await release.wait()
        effects.append(payload["n"])
        return True

    async def cheap(payload, progress):
        light.set()
        return True

    queue.register_task_handler(heavy_type, heavy)
    queue.register_task_handler("cheap", cheap)
    await queue.start()
    try:
        accepted = [
            await queue.enqueue_task(
                heavy_type, {"n": n, "streamer_name": f"channel-{n}"}
            )
            for n in range(100)
        ]
        await eventually(lambda: len(started) == 2)
        await queue.enqueue_task("cheap", {})
        await asyncio.wait_for(light.wait(), 2)
        assert len(queue.progress_tracker.active_tasks) <= (15 if isolated else 3)
        assert len(queue.dependency_manager.tasks) <= 15
        await queue.stop()
        assert not effects
        rows = store.snapshot(accepted)
        assert set(rows) == set(accepted)
        assert all(row.status == TaskStatus.PENDING for row in rows.values())
        release.set()
        await queue.start()
        await eventually(lambda: len(effects) == 100)
        await eventually(lambda: not queue.progress_tracker.active_tasks)
        assert sorted(effects) == list(range(100))
        assert all(
            row.status == TaskStatus.COMPLETED
            for row in store.snapshot(accepted).values()
        )
        assert all(row.progress == 100 for row in store.snapshot(accepted).values())
        await queue.stop()
        cold = TaskQueueManager(task_store=DurableTaskStore(sessions))
        try:
            await cold.start()
            assert set(accepted) <= set(cold.get_completed_tasks())
            assert cold.get_queue_statistics()["total_tasks"] == 101
        finally:
            await cold.stop()
    finally:
        release.set()
        await queue.stop()
        await queue.progress_tracker.cleanup_background_tasks()
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [False, True])
async def test_durable_retry_budget_and_dependencies(
    catalog_sessions, tmp_path, monkeypatch, isolated
):
    from app.services.queues.durable_task_store import DurableTaskStore

    from app.config.settings import get_settings

    sessions, _ = catalog_sessions
    engine = sessions.kw["bind"]
    monkeypatch.setattr(get_settings(), "RECORDING_DIRECTORY", str(tmp_path))
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    store = DurableTaskStore(sessions)
    queue = TaskQueueManager(
        max_workers=3, enable_streamer_isolation=isolated, task_store=store
    )
    attempts = []
    children = []

    async def flaky(payload, progress):
        attempts.append(1)
        if len(attempts) == 1:
            return False
        if len(attempts) == 2:
            raise RuntimeError("synthetic retry")
        return True

    async def child(payload, progress):
        children.append(len(attempts))
        return True

    queue.register_task_handler("flaky", flaky)
    queue.register_task_handler("child", child)
    await queue.start()
    try:
        parent = await queue.enqueue_task("flaky", {}, max_retries=2)
        dependent = await queue.enqueue_task_with_dependencies(
            "child", {}, dependencies=[parent]
        )
        await eventually(lambda: bool(children), timeout=20)
        assert attempts == [1, 1, 1]
        assert children == [3]
        await eventually(lambda: not queue.progress_tracker.active_tasks)
        stored = store.snapshot([parent, dependent])
        assert stored[parent].status == stored[dependent].status == TaskStatus.COMPLETED
        assert stored[parent].retry_count == 2
    finally:
        await queue.stop()
        await queue.progress_tracker.cleanup_background_tasks()
        engine.dispose()
