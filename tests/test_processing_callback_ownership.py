"""Actual factory task callbacks must not resolve default-peer resources."""

import asyncio
import importlib
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from starlette.requests import HTTPConnection
from sqlalchemy import event

from app import dependencies
from app.lifespan import (
    _close_application_logging,
    _close_application_proxy,
    _close_application_twitch,
)
from app.models import Recording, Stream
from app.services.queues.task_progress_tracker import TaskStatus
from app.services.recording.orphaned_recovery_service import OrphanedRecoveryService
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


async def close_owned(apps):
    for app in apps:
        await app.state.background_queue_manager.shutdown()
        await app.state.background_queue_service.stop()
        if app.state.recording_manager is not None:
            await app.state.recording_manager.shutdown()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await _close_application_logging(app)


@pytest.mark.asyncio
async def test_factory_cleanup_handler_writes_only_its_injected_owner_log(
    image_applications, monkeypatch
):
    apps, _, _, _ = image_applications
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    peer = await run_in_thread_pool(
        dependencies._get_application_logging_service, apps[1]
    )
    own_root = Path(apps[0].state.settings.LOGS_BASE_DIR)
    assert not own_root.exists()
    loop_thread = threading.get_ident()
    creation_threads = []
    native_mkdir = Path.mkdir

    def mkdir(path, *args, **kwargs):
        if path.is_relative_to(own_root):
            creation_threads.append(threading.get_ident())
        return native_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    logs = importlib.import_module("app.services.system.logging_service")
    monkeypatch.setattr(logs, "get_logging_service", lambda: peer)
    handler = apps[0].state.background_queue_manager.task_handlers
    file = (
        Path(apps[0].state.settings.RECORDING_DIRECTORY) / "remove-only-this-fixture.ts"
    )
    file.write_bytes(b"owned disposable cleanup fixture")

    def snapshot(root):
        return {str(path): path.read_bytes() for path in root.rglob("*.log")}

    before = snapshot(peer.logs_base_dir)
    try:
        await handler.handle_cleanup(
            {
                "stream_id": 70,
                "cleanup_paths": [str(file)],
                "streamer_name": "own-fixture",
            }
        )
        assert not file.exists()
        assert snapshot(peer.logs_base_dir) == before, (
            "App A handler wrote the default/peer B log"
        )
        assert any(
            b"DELETION_CLEANUP_START" in data for data in snapshot(own_root).values()
        )
        assert creation_threads and loop_thread not in creation_threads
    finally:
        await handler.cleanup()
        await close_owned(apps)


@pytest.mark.asyncio
async def test_registered_orphan_job_scans_its_own_catalogue_not_default_peer(
    image_applications, monkeypatch
):
    apps, databases, _, _ = image_applications
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    now = datetime.now(timezone.utc)

    def seed_peer():
        with databases[1].sync_session_factory() as db:
            for offset in range(3):
                path = (
                    Path(apps[1].state.settings.RECORDING_DIRECTORY)
                    / f"peer-{offset}.ts"
                )
                path.write_bytes(b"synthetic incomplete media")
                db.add(Stream(id=70 + offset, streamer_id=1, ended_at=now))
                db.flush()
                db.add(
                    Recording(
                        id=7 + offset,
                        stream_id=70 + offset,
                        status="stopped",
                        path=str(path),
                        start_time=now - timedelta(hours=1),
                    )
                )
            db.commit()

    await run_in_thread_pool(seed_peer)
    loop_thread = threading.get_ident()
    sql_threads = []

    def observe_sql(*args):
        sql_threads.append(threading.get_ident())

    for database in databases:
        event.listen(database.sync_engine, "before_cursor_execute", observe_sql)
    services = [
        await run_in_thread_pool(
            dependencies.get_application_recovery_service,
            HTTPConnection({"type": "http", "app": app}),
        )
        for app in apps
    ]
    adapter = OrphanedRecoveryService(services[1])

    async def peer_service():
        return adapter

    monkeypatch.setattr(
        importlib.import_module("app.services.recording.orphaned_recovery_service"),
        "get_orphaned_recovery_service",
        peer_service,
    )
    monkeypatch.setattr(
        importlib.import_module("app.services.init.background_queue_init"),
        "get_background_queue_service",
        lambda: apps[1].state.background_queue_service,
    )
    own = apps[0].state.background_queue_service
    manager = apps[0].state.background_queue_manager
    observed = []
    native_register = own.register_task_handler

    def register(kind, handler):
        if kind == "orphaned_recovery_check":

            async def observe(data, progress=None):
                result = await handler(data, progress)
                observed.append(result)
                return result

            native_register(kind, observe)
        else:
            native_register(kind, handler)

    monkeypatch.setattr(own, "register_task_handler", register)
    try:
        await manager.initialize()
        task_id = await own.enqueue_task(
            "orphaned_recovery_check", {"max_age_hours": 12}, max_retries=0
        )
        await asyncio.wait_for(own.wait_for_completion(), 15)
        assert own.get_task(task_id).status is TaskStatus.COMPLETED
        assert len(observed) == 1 and observed[0]["success"] is True
        assert observed[0]["orphaned_found"] == 0, (
            "Own empty catalogue was replaced by peer B recordings"
        )
        assert observed[0]["message"] == "No orphaned recordings found"
    finally:
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    assert sql_threads and loop_thread not in sql_threads
