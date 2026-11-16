"""Both real queue worker modes consume their factory's recovery scanner."""

import asyncio
import importlib
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [False, True])
async def test_factory_queue_recovery_uses_its_own_service_and_reports_failure(
    tmp_path, monkeypatch, isolated
):
    applications, databases, scans = [], [], []
    query_threads = []
    file_threads = []
    loop_thread = get_ident()
    module = importlib.import_module("app.services.recording.unified_recovery_service")

    async def forbidden_global():
        raise AssertionError("Queue borrowed the process-global recovery service")

    monkeypatch.setattr(module, "get_unified_recovery_service", forbidden_global)
    original_log = module.LoggingService.log_recording_activity_to_file

    def activity(service, *args, **kwargs):
        if args and args[0] == "SYSTEM_RECOVERY":
            file_threads.append(get_ident())
        return original_log(service, *args, **kwargs)

    monkeypatch.setattr(
        module.LoggingService, "log_recording_activity_to_file", activity
    )
    try:
        for index in range(2):
            root = tmp_path / str(index)
            root.mkdir()
            database = DatabaseLifecycle(f"sqlite:///{root / 'owned.db'}")
            databases.append(database)
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(root / "recordings"),
                    LOGS_BASE_DIR=str(root / "logs"),
                    _env_file=None,
                ),
                database=database,
            )
            applications.append(app)
            service = await run_in_thread_pool(
                dependencies.get_application_recovery_service,
                HTTPConnection({"type": "http", "app": app, "headers": []}),
            )
            original_scan = service.comprehensive_recovery_scan
            assert service.activity_logger is app.state.logging_service

            async def scan(*, owner=index, original=original_scan, **kwargs):
                scans.append(owner)
                if owner == 1:
                    raise RuntimeError("controlled-scan-fault")
                stats = await original(**kwargs)
                assert (
                    stats.recovered_recordings == stats.triggered_post_processing == 0
                )
                return stats

            monkeypatch.setattr(service, "comprehensive_recovery_scan", scan)
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: query_threads.append(get_ident()),
            )
            await app.state.background_queue_manager.initialize(
                enable_streamer_isolation=isolated
            )
        for index, app in enumerate(applications):
            queue = app.state.background_queue_service
            if index == 0:
                startup = importlib.import_module("app.services.init.startup_init")
                enqueued = []
                original_enqueue = queue.enqueue_task

                async def capture_enqueue(*args, **kwargs):
                    result = await original_enqueue(*args, **kwargs)
                    enqueued.append(result)
                    return result

                monkeypatch.setattr(queue, "enqueue_task", capture_enqueue)
                await startup.unified_recovery_scan(queue_service=queue)
                assert len(enqueued) == 1
                task_id = enqueued[0]
            else:
                task_id = await queue.enqueue_task(
                    "unified_recovery",
                    {"max_age_hours": 72, "dry_run": True},
                    max_retries=0,
                )

            async def finished():
                while task_id not in queue.completed_tasks:
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(finished(), 5)
            task = queue.completed_tasks[task_id]
            assert task.status.value == ("completed" if index == 0 else "failed")
            if index == 1:
                assert "controlled-scan-fault" in task.error_message
        assert scans == [0, 1]
        # Durable dispatch polls in closed workers; inspect quiescent shutdown,
        # not a random instant inside another legitimate journal transaction.
        for app in applications:
            await app.state.background_queue_manager.shutdown()
        assert query_threads and loop_thread not in query_threads
        assert file_threads and loop_thread not in file_threads
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        for app in applications:
            await app.state.background_queue_manager.shutdown()
            if app.state.twitch_api is not None:
                await app.state.twitch_api.close()
            await app.state.websocket_manager.close_all()
            if app.state.logging_service is not None:
                await run_in_thread_pool(app.state.logging_service.close)
        for database in databases:
            await database.adispose()
