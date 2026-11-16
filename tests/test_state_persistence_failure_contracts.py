"""Durable state failure/recovery semantics against isolated real SQL and native PIDs."""

from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys

import pytest
from sqlalchemy import event, update

from app.database import Base, DatabaseLifecycle
from app.models import ActiveRecordingState
from app.services.core.state_persistence_service import StatePersistenceService


@pytest.fixture
async def durable_state(tmp_path):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'durable.db'}")
    with database.sync_engine.begin() as connection:
        Base.metadata.create_all(connection)
    service = StatePersistenceService(session_factory=database.sync_session_factory)
    path = tmp_path / "owned.ts"
    path.write_bytes(b"owned")
    try:
        await service.save_active_recording(
            1, 1, os.getpid(), "fixture", "owned", datetime.now(timezone.utc), str(path)
        )
        yield service, database, path
    finally:
        await service.stop()
        await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["save", "remove", "heartbeat", "read", "cleanup", "refresh"]
)
async def test_state_query_failure_releases_transaction_and_preserves_retry(
    durable_state, operation
):
    service, database, path = durable_state

    def unavailable(*_args):
        raise OSError("synthetic durable state unavailable")

    event.listen(database.sync_engine, "before_cursor_execute", unavailable)
    try:
        if operation == "save":
            with pytest.raises(OSError, match="durable state unavailable"):
                await service.save_active_recording(
                    1,
                    1,
                    os.getpid(),
                    "new",
                    "changed",
                    datetime.now(timezone.utc),
                    str(path),
                )
        elif operation == "remove":
            assert not await service.remove_active_recording(1)
        elif operation == "heartbeat":
            assert not await service.update_heartbeat(1)
        elif operation == "read":
            assert await service.load_state() == []
        elif operation == "cleanup":
            assert await service.cleanup_stale_entries() == 0
        else:
            assert await service._refresh_heartbeats_for_live_processes() == 0
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", unavailable)
    assert database.sync_engine.pool.checkedout() == 0
    states = await service.load_state()
    assert len(states) == 1 and states[0].streamer_name == "owned"
    assert await service.update_heartbeat(1)
    assert path.read_bytes() == b"owned"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing-file", "dead-process"])
async def test_unrecoverable_state_is_removed_without_deleting_recording_bytes(
    durable_state, failure
):
    service, database, path = durable_state
    if failure == "missing-file":
        path.unlink()
    else:
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        assert child.wait(timeout=5) == 0
        assert not service._process_exists(child.pid)
        with database.sync_session_factory() as session:
            session.execute(update(ActiveRecordingState).values(process_id=child.pid))
            session.commit()
    assert await service.recover_active_recordings() == []
    assert await service.load_state() == []
    assert path.exists() is (failure == "dead-process")
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_stale_cleanup_and_empty_heartbeat_are_idempotent(durable_state):
    service, database, path = durable_state
    with database.sync_session_factory() as session:
        session.execute(
            update(ActiveRecordingState).values(
                last_heartbeat=datetime.now(timezone.utc) - timedelta(days=1)
            )
        )
        session.commit()
    assert await service.cleanup_stale_entries() == 1
    assert await service.cleanup_stale_entries() == 0
    assert await service._refresh_heartbeats_for_live_processes() == 0
    assert path.read_bytes() == b"owned"
    assert not service._process_exists(0) and not service._process_exists(-1)
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_repeated_start_keeps_the_existing_heartbeat_owner(durable_state):
    service, _, _ = durable_state
    await service.start()
    original = service.heartbeat_task
    await service.start()
    assert original is service.heartbeat_task and service.is_running
    await service.stop()
    assert original.done() and not service.is_running
    await service.stop()
