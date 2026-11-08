"""Kernel fencing preserves live/unknown peers without depending on hostname."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import time
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.models.background_task import BackgroundTask, BackgroundTaskDependency
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_progress_tracker import (
    QueueTask,
    TaskPriority,
    TaskStatus,
)


from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions = _catalog_sessions


@pytest.fixture
def stores(catalog_sessions, tmp_path, monkeypatch):
    from app.config.settings import get_settings

    sessions, backend = catalog_sessions
    engine = sessions.kw["bind"]
    monkeypatch.setattr(get_settings(), "RECORDING_DIRECTORY", str(tmp_path))
    with engine.begin() as connection:
        if backend == "sqlite":
            connection.exec_driver_sql("BEGIN")
        BackgroundTask.__table__.create(connection)
        BackgroundTaskDependency.__table__.create(connection)
    owners = []

    def owner():
        store = DurableTaskStore(sessions)
        owners.append(store)
        return store

    yield engine, sessions, owner
    for store in owners:
        store.close_owner()
    engine.dispose()


def task(identifier):
    return QueueTask(
        id=identifier,
        task_type="cheap",
        priority=TaskPriority.NORMAL,
        payload={},
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )


def test_live_peer_and_inherited_descriptor_cannot_be_reclaimed(stores):
    _, _, new = stores
    live, peer = new(), new()
    live.accept([(task("live"), set(), "synthetic")])
    live.host = "a-different-container"
    assert len(live.claim(1, set(), 1, True)) == 1
    peer.recover()
    assert peer.snapshot(["live"])["live"].status is TaskStatus.RUNNING
    inherited = os.dup(live.owner_fd)
    try:
        live.close_owner()
        peer.recover()
        assert peer.snapshot(["live"])["live"].status is TaskStatus.RUNNING
    finally:
        os.close(inherited)
    peer.recover()
    assert peer.snapshot(["live"])["live"].status is TaskStatus.PENDING


@pytest.mark.parametrize("token", [None, "malformed-owner", str(uuid4())])
def test_uninspectable_peer_stays_running(stores, token):
    _, sessions, new = stores
    store = new()
    store.accept([(task("unknown"), set(), "synthetic")])
    with sessions() as db:
        row = db.get(BackgroundTask, "unknown")
        row.status, row.owner_token, row.owner_host = "running", token, "uninspectable"
        db.commit()
    store.recover()
    assert store.snapshot(["unknown"])["unknown"].status is TaskStatus.RUNNING


@pytest.mark.parametrize("isolated", [False, True])
def test_live_peer_claims_share_global_capacity_and_streamer_isolation(
    stores, isolated
):
    _, _, new = stores
    first, second = new(), new()
    first.accept([(task(f"same-channel-{n}"), set(), "one-channel") for n in range(4)])
    assert len(first.claim(1, set(), 1, isolated, global_capacity=3)) == 1
    claimed = second.claim(3, set(), 2, isolated, global_capacity=3)
    assert len(claimed) == (0 if isolated else 2)


@pytest.mark.asyncio
async def test_started_queue_recovers_after_inherited_peer_fd_is_released(stores):
    import asyncio
    from app.services.queues.task_queue_manager import TaskQueueManager

    _, _, new = stores
    old, peer = new(), new()
    old.accept([(task("release-later"), set(), "synthetic")])
    assert len(old.claim(1, set(), 1, False)) == 1
    inherited = os.dup(old.owner_fd)
    old.close_owner()
    queue = TaskQueueManager(task_store=peer)
    effects = []

    async def handler(payload, progress):
        effects.append(True)
        return True

    queue.register_task_handler("cheap", handler)
    await queue.start()
    try:
        assert (
            peer.snapshot(["release-later"])["release-later"].status
            is TaskStatus.RUNNING
        )
        os.close(inherited)
        inherited = None
        async with asyncio.timeout(8):
            while (
                peer.snapshot(["release-later"])["release-later"].status
                is not TaskStatus.COMPLETED
            ):
                await asyncio.sleep(0.05)
        assert effects == [True]
    finally:
        if inherited is not None:
            os.close(inherited)
        await queue.stop()
        await queue.progress_tracker.cleanup_background_tasks()


def test_concurrent_sqlite_dispatchers_never_acknowledge_the_same_claim(stores):
    engine, _, new = stores
    seed = new()
    seed.accept([(task(f"job-{n}"), set(), f"streamer-{n}") for n in range(100)])
    owners = [new() for _ in range(10)]

    def delayed_update(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE background_tasks"):
            time.sleep(0.002)  # widen a real SQLite read/update race, no fake DB

    event.listen(engine, "before_cursor_execute", delayed_update)

    def claim(store):
        return [
            entry[0].id for _ in range(10) for entry in store.claim(1, set(), 1, False)
        ]

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(claim, owners))
    ids = [identifier for batch in results for identifier in batch]
    assert len(ids) == 100
    assert len(set(ids)) == 100
