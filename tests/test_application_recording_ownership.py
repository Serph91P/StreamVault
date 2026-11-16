"""The production factory/provider binding must not construct a global recorder."""

import asyncio
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
async def test_factory_recording_provider_and_lifespan_resolve_the_same_owned_actor(
    tmp_path,
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    applications = [
        create_app(
            settings=Settings(
                ENVIRONMENT="test",
                RECORDING_DIRECTORY=str(tmp_path / name),
                _env_file=None,
            ),
            database=database,
        )
        for name, database in zip(("first", "second"), databases, strict=True)
    ]
    managers = []
    query_threads = []
    loop_thread = get_ident()
    try:
        for app, database in zip(applications, databases, strict=True):
            assert getattr(app.state, "recording_manager", None) is None
            assert database._sync_engine is None
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: query_threads.append(get_ident()),
            )
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            candidates = await asyncio.gather(
                *(
                    run_in_thread_pool(
                        dependencies.get_application_recording_manager, connection
                    )
                    for _ in range(3)
                )
            )
            assert all(candidate is candidates[0] for candidate in candidates)
            manager = candidates[0]
            managers.append(manager)
            assert app.state.recording_manager is manager
            provider = dependencies.get_lifespan_service(
                app, dependencies.get_recording_manager
            )
            assert await run_in_thread_pool(provider) is manager
            orchestrator = manager.orchestrator
            assert (
                orchestrator.websocket_service.websocket_manager
                is app.state.websocket_manager
            )
            assert (
                orchestrator.post_processing_coordinator.queue_service
                is app.state.background_queue_service
            )
            assert (
                manager._upstream_coordinator
                is manager.process_manager.upstream_coordinator
            )
            assert (
                manager.recording_service.recordings_directory
                == app.state.settings.RECORDING_DIRECTORY
            )
            assert await manager.reconcile_leases() == 0
            assert database.sync_engine.pool.checkedout() == 0
        assert managers[0] is not managers[1]
        assert managers[0].process_manager is not managers[1].process_manager
        assert (
            managers[0].orchestrator.state_manager
            is not managers[1].orchestrator.state_manager
        )
        managers[0].orchestrator.state_manager.add_active_recording(1, {"stream_id": 1})
        assert managers[1].get_active_recordings() == {}
        managers[0].orchestrator.state_manager.clear_all_state()
        assert query_threads and loop_thread not in query_threads
    finally:
        for manager in managers:
            await manager.process_manager.cleanup_all()
        for app in applications:
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()
            await app.state.websocket_manager.close_all()
        for database in databases:
            await database.adispose()
