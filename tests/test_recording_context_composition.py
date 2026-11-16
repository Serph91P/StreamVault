"""Real recording facades bind persistence, completion queues and sockets together."""

import asyncio
import json
import os
from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event, select
from starlette.websockets import WebSocket

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.services.background_queue_service import BackgroundQueueService
from app.services.communication.websocket_manager import ConnectionManager
from app.services.recording.recording_orchestrator import RecordingOrchestrator
from app.services.recording.recording_service import RecordingService
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.parametrize(
    "missing", ["settings", "session_factory", "connection_manager", "queue_service"]
)
def test_recording_context_rejects_partial_global_fallback(missing):
    def no_sessions():
        raise AssertionError("partial context must fail before opening a session")

    manager = ConnectionManager()
    context = {
        "settings": Settings(ENVIRONMENT="test", _env_file=None),
        "session_factory": no_sessions,
        "connection_manager": manager,
        "queue_service": BackgroundQueueService.for_application(manager),
    }
    context.pop(missing)
    with pytest.raises(ValueError, match="context requires"):
        RecordingOrchestrator(**context)


@pytest.mark.asyncio
async def test_recording_composition_keeps_database_callbacks_queue_and_socket_owned(
    tmp_path,
    monkeypatch,
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    managers = [ConnectionManager(), ConnectionManager()]
    queues = [BackgroundQueueService.for_application(manager) for manager in managers]
    outgoing = [asyncio.Queue(), asyncio.Queue()]
    facades = []
    queries = []
    probes = []
    native_lstat = os.lstat
    loop_thread = get_ident()

    def lstat(candidate, *args, **kwargs):
        if isinstance(candidate, (str, os.PathLike)) and str(candidate).startswith(
            str(tmp_path)
        ):
            probes.append(get_ident())
        return native_lstat(candidate, *args, **kwargs)

    async def receive():
        return {"type": "websocket.connect"}

    try:
        for index, database in enumerate(databases):
            root = tmp_path / ("recordings" + str(index))
            root.mkdir()
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(
                    Streamer(id=1, username="owner" + str(index), twitch_id=str(index))
                )
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
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            settings = Settings(
                ENVIRONMENT="test", RECORDING_DIRECTORY=str(root), _env_file=None
            )
            orchestrator = await run_in_thread_pool(
                RecordingOrchestrator,
                settings=settings,
                session_factory=database.sync_session_factory,
                connection_manager=managers[index],
                queue_service=queues[index],
            )
            facade = RecordingService(orchestrator=orchestrator)
            facades.append(facade)
            assert facade.recordings_directory == str(root)
            assert facade.config_manager._settings is settings
            socket = WebSocket(
                {
                    "type": "websocket",
                    "path": "/ws",
                    "headers": [],
                    "client": ("127.0.0.1", 12345),
                },
                receive,
                outgoing[index].put,
            )
            await managers[index].connect(socket)
            assert (await outgoing[index].get())["type"] == "websocket.accept"
            connected = await asyncio.wait_for(outgoing[index].get(), 2)
            assert json.loads(connected["text"])["type"] == "connection.status"
        assert facades[0].process_manager is not facades[1].process_manager
        assert facades[0].active_recordings is not facades[1].active_recordings
        for index, facade in enumerate(facades):
            path = str(tmp_path / ("recordings" + str(index)) / "capture.ts")
            with monkeypatch.context() as watched:
                watched.setattr(os, "lstat", lstat)
                await facade.process_manager.post_processing_callback(1, path)
            completed = await facade.orchestrator.database_service.get_recording(1)
            assert completed.status == "completed" and completed.path == path
            tasks = queues[index].queue_manager.dependency_manager.tasks
            assert tasks and all(
                task.payload["streamer_name"] == "owner" + str(index)
                for task in tasks.values()
            )

            def saved_ids():
                with databases[index].sync_session_factory() as session:
                    state = session.scalar(
                        select(RecordingProcessingState).where(
                            RecordingProcessingState.recording_id == 1
                        )
                    )
                    assert state is not None
                    return state.get_task_ids()

            assert await run_in_thread_pool(saved_ids) == {
                task.type: task.id for task in tasks.values()
            }
            frame = await asyncio.wait_for(outgoing[index].get(), 2)
            assert frame["type"] == "websocket.send"
            assert json.loads(frame["text"])["type"] == "recording_job_update"
            if index == 0:
                assert not queues[1].queue_manager.dependency_manager.tasks
                assert outgoing[1].empty()
                peer = await facades[1].orchestrator.database_service.get_recording(1)
                assert peer.status == "recording" and peer.path is None
            assert databases[index].sync_engine.pool.checkedout() == 0
        first_ids = set(queues[0].queue_manager.dependency_manager.tasks)
        second_ids = set(queues[1].queue_manager.dependency_manager.tasks)
        assert first_ids == second_ids
        assert all(
            queues[0].queue_manager.dependency_manager.tasks[task_id]
            is not queues[1].queue_manager.dependency_manager.tasks[task_id]
            for task_id in first_ids
        )
        assert queries and loop_thread not in queries
        assert probes and loop_thread not in probes
    finally:
        for facade in facades:
            await facade.process_manager.cleanup_all()
        for manager in managers:
            await manager.close_all()
        for database in databases:
            await database.adispose()
