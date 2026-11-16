"""App-local recording state task cancellation and recovery use real tasks/catalogues."""

import asyncio
from datetime import datetime, timezone

import pytest

from sqlalchemy import select

from app.database import Base, DatabaseLifecycle
from app.models import Recording, Stream, Streamer
from app.services.core.state_persistence_service import StatePersistenceService
from app.services.recording.config_manager import ConfigManager
from app.services.recording.recording_database_service import RecordingDatabaseService
from app.services.recording.recording_state_manager import RecordingStateManager


@pytest.mark.asyncio
async def test_state_tracking_cancellation_and_finished_cleanup_keep_peer_alive(
    tmp_path,
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'state.db'}")
    persistence = StatePersistenceService(session_factory=database.sync_session_factory)
    owner = RecordingStateManager.for_application(ConfigManager(), persistence)
    peer = RecordingStateManager.for_application(ConfigManager(), persistence)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def held():
        entered.set()
        await release.wait()

    tasks = [asyncio.create_task(held()) for _ in range(3)]
    try:
        await entered.wait()
        owner.add_recording_task(1, tasks[0])
        owner.add_recording_task(2, tasks[1])
        peer.add_recording_task(1, tasks[2])
        owner.add_active_recording(1, {"file_path": "owned.ts"})
        owner.update_active_recording(1, {"progress": 20})
        owner.update_active_recording(99, {"progress": 90})
        assert owner.get_active_recording(1)["progress"] == 20
        assert owner.get_active_recording(99) is None
        copy = owner.get_active_recordings()
        copy.clear()
        assert owner.get_active_recording_count() == 1
        assert owner.get_recording_task(1) is tasks[0]
        task_copy = owner.get_active_tasks()
        task_copy.clear()
        assert owner.get_recording_statistics() == {
            "active_recordings": 1,
            "active_tasks": 2,
        }
        assert not owner.cancel_recording_task(99)
        assert owner.cancel_recording_task(1)
        await asyncio.gather(tasks[0], return_exceptions=True)
        assert not owner.cancel_recording_task(1)
        assert owner.cleanup_finished_tasks() == [1]
        assert owner.cleanup_finished_tasks() == []
        assert owner.cancel_all_tasks() == [2]
        await asyncio.gather(tasks[1], return_exceptions=True)
        assert owner.cancel_all_tasks() == []
        assert owner.remove_recording_task(2) is tasks[1]
        assert owner.remove_recording_task(2) is None
        assert not tasks[2].done()
        assert owner.remove_active_recording(1)["file_path"] == "owned.ts"
        assert owner.remove_active_recording(1) is None
        owner.add_active_recording(3, {"file_path": "again.ts"})
        owner.clear_all_state()
        assert owner.get_recording_statistics() == {
            "active_recordings": 0,
            "active_tasks": 0,
        }
        assert peer.get_recording_task(1) is tasks[2] and not tasks[2].done()
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["missing-recording", "missing-file", "empty-state", "database-failure"]
)
async def test_state_recovery_failure_is_bounded_and_keeps_peer_catalogue(
    tmp_path, case
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'recovery.db'}")
    persistence = StatePersistenceService(session_factory=database.sync_session_factory)
    owner = RecordingStateManager.for_application(ConfigManager(), persistence)
    service = RecordingDatabaseService(session_factory=database.sync_session_factory)
    try:
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="scoped", twitch_id="scoped"))
            session.flush()
            session.add(Stream(id=1, streamer_id=1))
            session.flush()
            session.add(
                Recording(
                    id=1,
                    stream_id=1,
                    status="recording",
                    start_time=datetime.now(timezone.utc),
                )
            )
            session.commit()
        if case == "missing-recording":
            assert not await owner._recover_single_recording(99, {}, service)
        elif case == "missing-file":
            assert not await owner._recover_single_recording(
                1, {"file_path": str(tmp_path / "gone.ts")}, service
            )
            with database.sync_session_factory() as session:
                assert session.get(Recording, 1).status == "failed"
        elif case == "empty-state":
            assert await owner.load_state_from_persistence() == {}
            assert await owner.recover_active_recordings_from_persistence(service) == []
        else:
            database.sync_engine.dispose()
            with database.sync_engine.begin() as connection:
                Recording.__table__.drop(connection)
            assert not await owner._recover_single_recording(1, {}, service)
        assert owner.get_active_recording_count() == 0
        assert database.sync_engine.pool.checkedout() == 0
        with database.sync_session_factory() as session:
            assert (
                session.scalar(select(Streamer.username).where(Streamer.id == 1))
                == "scoped"
            )
    finally:
        await database.adispose()
