"""Queue initialization must own the actual workers, handlers and recovery loop."""

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from threading import get_ident

import pytest
from sqlalchemy import event, select
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.utils.async_db_utils import run_in_thread_pool

from app.models import (
    Recording,
    RecordingProcessingState,
    Stream,
    Streamer,
    StreamEvent,
)
from app.services.background_queue_service import BackgroundQueueService
from app.services.communication.websocket_manager import ConnectionManager
from app.services.init.background_queue_init import (
    BackgroundQueueManager,
    background_queue_manager,
)
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("composition", ["explicit", "factory"])
async def test_queue_managers_execute_owned_chapters_and_stop_without_stopping_peer(
    tmp_path, monkeypatch, isolated, composition
):
    monkeypatch.setenv("STREAMVAULT_ENABLE_STREAMER_ISOLATION", str(isolated).lower())
    startup_init = importlib.import_module("app.services.init.startup_init")
    recovery_module = importlib.import_module(
        "app.services.automatic_queue_recovery_service"
    )
    legacy_recovery = recovery_module._recovery_service
    legacy_running = background_queue_manager.is_running()
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    managers = []
    recording_managers = []
    sockets = []
    queries = []
    loop_thread = get_ident()
    started = datetime(2026, 10, 1, tzinfo=timezone.utc)
    try:
        for index, database in enumerate(databases):
            recorder = None
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username="alice", twitch_id="alice"))
                session.flush()
                session.add(
                    Stream(
                        id=1,
                        streamer_id=1,
                        title=f"owned-{index}",
                        started_at=started,
                        ended_at=started + timedelta(minutes=1),
                    )
                )
                session.flush()
                session.add(
                    Recording(id=1, stream_id=1, status="completed", start_time=started)
                )
                session.add(
                    StreamEvent(
                        stream_id=1,
                        timestamp=started,
                        title=f"owned-{index}",
                        category_name=f"category-{index}",
                        event_type="channel.update",
                    )
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            if composition == "factory":
                app = create_app(
                    settings=Settings(
                        ENVIRONMENT="test",
                        RECORDING_DIRECTORY=str(tmp_path / str(index)),
                        _env_file=None,
                    ),
                    database=database,
                )
                manager = app.state.background_queue_manager
                queue = app.state.background_queue_service
                handlers = manager.task_handlers
                socket = app.state.websocket_manager
                assert manager.queue_service is queue
                recorder = await run_in_thread_pool(
                    dependencies.get_application_recording_manager,
                    HTTPConnection({"type": "http", "app": app, "headers": []}),
                )
                recording_managers.append(recorder)
            else:
                socket = ConnectionManager()
                queue = BackgroundQueueService.for_application(socket)
                handlers = PostProcessingTaskHandlers(
                    session_factory=database.sync_session_factory,
                    connection_manager=socket,
                )
                manager = BackgroundQueueManager(
                    queue_service=queue, task_handlers=handlers
                )
            sockets.append(socket)
            managers.append(manager)
            if composition == "factory":
                assert recorder is not None
                await startup_init.initialize_background_queue_with_fixes(
                    queue_manager=manager, capture_checker=recorder.is_capture_running
                )
                assert queue.capture_checker.__self__ is recorder
                assert await startup_init.verify_queue_readiness(queue_service=queue)
            else:
                await manager.initialize(enable_streamer_isolation=isolated)
            assert manager.is_running()
            assert manager.recovery_service.background_queue_service is queue
            assert manager.recovery_service.recovery_task is not None
            assert queue.task_handlers["chapters_generation"].__self__ is handlers
            assert len(queue.task_handlers) == 9
        assert managers[0].recovery_service is not managers[1].recovery_service
        assert (
            managers[0].recovery_service.recovery_task
            is not managers[1].recovery_service.recovery_task
        )
        for index, manager in enumerate(managers):
            directory = tmp_path / "alice" / str(index)
            directory.mkdir(parents=True)
            task_id = await manager.queue_service.enqueue_task(
                "chapters_generation",
                {
                    "stream_id": 1,
                    "recording_id": 1,
                    "streamer_name": "alice",
                    "mp4_path": str(directory / "episode.mp4"),
                },
                max_retries=0,
            )

            async def finished():
                while task_id not in manager.queue_service.completed_tasks:
                    await asyncio.sleep(0.02)

            await asyncio.wait_for(finished(), 10)
            assert (
                manager.queue_service.completed_tasks[task_id].status.value
                == "completed"
            )
            generated = directory / "episode.vtt"
            assert f"category-{index}" in generated.read_text()
            assert f"category-{1 - index}" not in generated.read_text()
        assert queries and loop_thread not in queries
        for database in databases:
            with database.sync_session_factory() as session:
                assert (
                    session.scalar(select(RecordingProcessingState)).chapters_status
                    == "completed"
                )
        await managers[0].shutdown()
        assert databases[0].sync_engine.pool.checkedout() == 0
        assert not managers[0].is_running()
        assert managers[0].recovery_service.recovery_task.done()
        assert managers[1].is_running()
        assert not managers[1].recovery_service.recovery_task.done()
        assert background_queue_manager.is_running() is legacy_running
        assert recovery_module._recovery_service is legacy_recovery
    finally:
        for manager in managers:
            await manager.shutdown()
        for recorder in recording_managers:
            await recorder.shutdown()
        for socket in sockets:
            await socket.close_all()
        for database in databases:
            # A live peer dispatcher may borrow a connection; shutdown is the leak boundary.
            assert database.sync_engine.pool.checkedout() == 0
            await database.adispose()


@pytest.mark.parametrize("resource", ["queue_service", "task_handlers"])
def test_queue_manager_rejects_partial_application_context(resource):
    with pytest.raises(ValueError, match="together"):
        BackgroundQueueManager(**{resource: object()})
