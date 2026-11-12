"""Public/legacy recording facade adapters retain actual DB, state and socket effects."""

from datetime import datetime, timezone

import pytest

from app.models import Recording, Stream
from app.services.recording.recording_orchestrator import RecordingOrchestrator
from app.services.system.logging_service import LoggingService
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
async def test_orchestrator_compatibility_operations_keep_owned_catalogue_and_realtime(
    image_applications, tmp_path
):
    apps, databases, _, _ = image_applications
    owners, loggers = [], []
    try:
        for index, (app, database) in enumerate(zip(apps, databases, strict=True)):
            with database.sync_session_factory() as session:
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
            logger = await run_in_thread_pool(
                LoggingService, str(tmp_path / f"logs-{index}"), isolated=True
            )
            loggers.append(logger)
            owners.append(
                await run_in_thread_pool(
                    RecordingOrchestrator,
                    settings=app.state.settings,
                    session_factory=database.sync_session_factory,
                    connection_manager=app.state.websocket_manager,
                    queue_service=app.state.background_queue_service,
                    logging_service=logger,
                )
            )
        owner, peer = owners
        assert not owner.is_shutting_down() and not peer.is_shutting_down()
        assert owner.get_recording_statistics()["service_status"]["database_service"]
        assert owner.get_recording_statistics()["active_recordings"] == 0
        assert await owner.recover_active_recordings_from_persistence() == []
        assert await owner.cleanup_all_recordings() == []
        await owner._force_stop_all_recordings()
        assert owner.cleanup_finished_tasks() == [] and owner._cancel_all_tasks() == []
        path = tmp_path / "owned.ts"
        path.write_bytes(b"preserve media")
        assert await owner._recover_single_recording(1, {"file_path": str(path)})
        assert owner.get_active_recordings()[1]["recovered"] is True
        assert peer.get_active_recordings() == {}
        await owner.send_active_recordings_websocket_update()
        await owner._send_recording_job_update(1, "recording", "running", 25)
        await owner._send_background_task_update(
            "owned-task", "metadata", "running", 50
        )
        assert owner.websocket_service.is_websocket_available()
        assert not apps[1].state.websocket_manager._event_log
        await owner.update_recording_status(1, "processing", str(path), 10)
        await owner.ensure_stream_ended(1)
        with databases[0].sync_session_factory() as session:
            row = session.get(Recording, 1)
            assert (
                row.status == "processing"
                and row.duration == 10
                and row.path == str(path)
            )
            assert session.get(Stream, 1).ended_at is not None
        with databases[1].sync_session_factory() as session:
            assert session.get(Recording, 1).status == "recording"
            assert session.get(Stream, 1).ended_at is None
        await owner._update_recording_status(1, "completed", str(path), 12)
        await owner._ensure_stream_ended(1)
        with databases[0].sync_session_factory() as session:
            assert session.get(Recording, 1).status == "completed"
            assert session.get(Recording, 1).duration == 12
        await owner.process_manager.post_processing_callback(999, str(path))
        owner.state_manager.clear_all_state()
        await owner.graceful_shutdown()
        await owner.wait_for_shutdown()
        assert owner.is_shutting_down() and not peer.is_shutting_down()
        assert path.read_bytes() == b"preserve media"
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        for owner in owners:
            await owner.graceful_shutdown()
        for logger in loggers:
            await run_in_thread_pool(logger.close)
