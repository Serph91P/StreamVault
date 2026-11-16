"""Actual mounted orphaned recovery reads and queues only its own catalogue.

Synthetic TS bytes exercise durable admission, not decoding or media completion.
"""

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import (
    _close_application_logging,
    _close_application_proxy,
    _close_application_twitch,
)
from app.models import BackgroundTask, Recording, Stream
from app.services.recording.orphaned_recovery_service import OrphanedRecoveryService
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    ["statistics", "scan", "single", "single-protected", "single-queue-failure"],
)
async def test_admin_recovery_preserves_closed_owner_catalogue_and_durable_admission(
    image_applications, monkeypatch, operation
):
    apps, databases, clients, queries = image_applications
    now = datetime.now(timezone.utc)
    roots = [Path(app.state.settings.RECORDING_DIRECTORY) for app in apps]
    for app, root in zip(apps, roots, strict=True):
        monkeypatch.setattr(app.state.settings, "LOGS_BASE_DIR", str(root / ".logs"))

    def seed():
        for index, database in enumerate(databases):
            with database.sync_session_factory() as session:
                for offset in range(1 if index == 0 else 3):
                    path = roots[index] / f"fixture-{offset}.ts"
                    path.write_bytes(
                        b"tiny"
                        if index == 1 and offset == 0
                        else b"synthetic TS fixture" * 128
                    )
                    session.add(
                        Stream(
                            id=70 + offset,
                            streamer_id=1,
                            started_at=now - timedelta(hours=2),
                            ended_at=now - timedelta(hours=1),
                        )
                    )
                    session.flush()
                    session.add(
                        Recording(
                            id=7 + offset,
                            stream_id=70 + offset,
                            status="recording"
                            if index == 0 and operation == "single-protected"
                            else "stopped",
                            path=str(path),
                            start_time=now - timedelta(hours=2),
                        )
                    )
                session.commit()

    await run_in_thread_pool(seed)
    services = [
        await run_in_thread_pool(
            dependencies.get_application_recovery_service,
            HTTPConnection({"type": "http", "app": app}),
        )
        for app in apps
    ]
    peer_adapter = OrphanedRecoveryService(service=services[1])

    async def default_peer():
        return peer_adapter

    monkeypatch.setattr(
        importlib.import_module("app.services.recording.orphaned_recovery_service"),
        "get_orphaned_recovery_service",
        default_peer,
    )
    monkeypatch.setattr(
        importlib.import_module("app.database"),
        "SessionLocal",
        databases[1].sync_session_factory,
    )
    monkeypatch.setattr(
        dependencies, "get_recording_manager", lambda: services[1]._recording_owner()
    )

    def jobs(database):
        with database.sync_session_factory() as session:
            return [
                (row.status, row.payload) for row in session.query(BackgroundTask).all()
            ]

    queue_init = importlib.import_module("app.services.init.background_queue_init")
    native_enqueue = queue_init.enqueue_recording_post_processing

    async def observe_admission(**payload):
        from sqlalchemy import inspect

        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        assert all(inspect(value, raiseerr=False) is None for value in payload.values())
        return await native_enqueue(**payload)

    monkeypatch.setattr(
        queue_init, "enqueue_recording_post_processing", observe_admission
    )
    queries.clear()
    try:
        if operation.startswith("single"):
            from sqlalchemy import event

            def reject_job(_conn, _cursor, sql, *_):
                if sql.lstrip().upper().startswith("INSERT INTO BACKGROUND_TASKS"):
                    raise RuntimeError("synthetic-owned-recovery-admission-fault")

            if operation == "single-queue-failure":
                event.listen(
                    databases[0].sync_engine, "before_cursor_execute", reject_job
                )
            try:
                response = await clients[0].post("/api/admin/orphaned/recover/7")
            finally:
                if operation == "single-queue-failure":
                    event.remove(
                        databases[0].sync_engine, "before_cursor_execute", reject_job
                    )
            assert response.status_code == 200
            own_jobs = await run_in_thread_pool(jobs, databases[0])
            if operation == "single":
                assert response.json()["success"] is True
                assert response.json()["data"]["file_path"] == str(
                    roots[0] / "fixture-0.ts"
                )
                assert own_jobs and all(status != "completed" for status, _ in own_jobs)
                assert str(roots[0]) in json.dumps(own_jobs)
                assert str(roots[1]) not in json.dumps(own_jobs)
            else:
                assert response.json()["success"] is False and own_jobs == []
                if operation == "single-protected":
                    assert "ownership is unverified" in response.json()["message"]
        else:
            response = await (
                clients[0].get("/api/admin/orphaned/statistics")
                if operation == "statistics"
                else clients[0].post("/api/admin/orphaned/scan?dry_run=true")
            )
            assert response.status_code == 200 and response.json()["success"] is True
            field = (
                "failed_post_processing"
                if operation == "statistics"
                else "orphaned_found"
            )
            # Scan's orphaned_found counts segment dirs; failed TS files are exposed
            # through the same adapter's statistics response.
            if operation == "statistics":
                assert response.json()["data"][field] == 1
            else:
                assert response.json()["data"]["recovery_triggered"] == 0
                assert services[0].is_running is False
                own_log = Path(apps[0].state.settings.LOGS_BASE_DIR)
                assert any(
                    "failed_pp=1" in path.read_text() for path in own_log.rglob("*.log")
                )
            assert await run_in_thread_pool(jobs, databases[0]) == []
        assert await run_in_thread_pool(jobs, databases[1]) == []
        assert queries and get_ident() not in {thread for thread, _ in queries}
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for app in apps:
            if app.state.recording_manager is not None:
                await app.state.recording_manager.shutdown()
            await app.state.background_queue_service.stop()
            await _close_application_proxy(app)
            await _close_application_twitch(app)
            await _close_application_logging(app)
