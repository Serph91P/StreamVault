"""Startup and mandatory readiness reflect only the owning app's lifecycle."""

from pathlib import Path
import asyncio
from threading import get_ident

import pytest

from app import dependencies
from app.services.system.supervisor import TaskSupervisor
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications
MANDATORY = {
    "startup",
    "migrations",
    "critical_services",
    "recordings_path",
    "persistent_keys",
}


@pytest.mark.asyncio
async def test_existing_protected_diagnostics_keep_failure_type_local(
    image_applications,
):
    import httpx

    apps, _, clients, _ = image_applications
    apps[0].state.startup_failure = "RuntimeError"
    apps[0].state.startup_phases = ["migrations"]
    first = await clients[0].get("/api/status/health")
    peer = await clients[1].get("/api/status/health")
    assert first.status_code == peer.status_code == 200
    assert first.json()["lifecycle"]["startup_failure"] == "RuntimeError"
    assert first.json()["lifecycle"]["completed_phases"] == ["migrations"]
    assert peer.json()["lifecycle"]["startup_failure"] is None
    assert apps[0].state.settings.RECORDING_DIRECTORY not in first.text
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=apps[0]),
        base_url=clients[0].base_url,
        headers={"Accept": "application/json"},
    ) as anonymous:
        assert (await anonymous.get("/api/status/health")).status_code == 401


@pytest.mark.asyncio
async def test_startup_is_app_local_and_never_bootstraps_from_getter(
    image_applications, monkeypatch
):
    from app.utils import proxy_encryption

    apps, _, clients, queries = image_applications

    def forbidden(*args, **kwargs):
        raise AssertionError("startup getter attempted identity bootstrap")

    monkeypatch.setattr(proxy_encryption, "bootstrap_proxy_identity", forbidden)
    queries.clear()
    for client in clients:
        response = await client.get("/api/health/startup")
        assert response.status_code == 503
        assert response.json() == {"status": "not_started"}
    apps[0].state.startup_complete = True
    first = await clients[0].get("/api/health/startup")
    peer = await clients[1].get("/api/health/startup")
    assert first.status_code == 200 and first.json() == {"status": "startup_complete"}
    assert peer.status_code == 503
    assert not queries
    apps[0].state.startup_complete = False
    assert (await clients[0].get("/api/health/startup")).status_code == 503
    assert (await clients[0].get("/api/health/live")).json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_database_only_policy_cannot_hide_unknown_startup_or_identity(
    image_applications,
):
    apps, _, clients, _ = image_applications
    apps[0].state.settings.READINESS_REQUIRED_COMPONENTS = ["database"]
    response = await clients[0].get("/api/health/ready")
    assert response.status_code == 503
    assert set(response.json()["checks"]) == MANDATORY | {"database"}
    assert response.json()["checks"]["startup"] == "unavailable"
    assert response.json()["checks"]["migrations"] == "unavailable"
    assert response.json()["checks"]["persistent_keys"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_tracks_owned_queue_tasks_phases_and_path_without_creating_files(
    image_applications, monkeypatch
):
    from sqlalchemy import event

    apps, databases, clients, queries = image_applications
    app = apps[0]
    supervisor = TaskSupervisor("readiness-unit")
    app.state.task_supervisor = supervisor
    app.state.startup_phases = [
        "migrations",
        "persistent-identities",
        "core-services",
        "background-services",
        "ready",
    ]
    app.state.startup_complete = True
    app.state.settings.READINESS_REQUIRED_COMPONENTS = ["database"]
    stat_threads = []
    import os

    native_stat = os.stat
    root = Path(app.state.settings.RECORDING_DIRECTORY)

    def stat(path, *args, **kwargs):
        if not isinstance(path, int) and Path(path) == root:
            stat_threads.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", stat)
    provider = dependencies.get_lifespan_service(
        app, dependencies.get_recording_manager
    )
    await run_in_thread_pool(provider)
    await app.state.background_queue_service.start()
    try:
        queries.clear()
        response = await clients[0].get("/api/health/ready")
        assert response.status_code == 200, response.text
        assert all(value == "ready" for value in response.json()["checks"].values())
        assert queries and all(thread != get_ident() for thread, _ in queries)
        assert stat_threads and get_ident() not in stat_threads
        assert (await clients[1].get("/api/health/ready")).status_code == 503
        app.state.settings.READINESS_REQUIRED_COMPONENTS = []

        def unavailable(_, __, statement, *___):
            if statement.strip() == "SELECT 1":
                raise RuntimeError("synthetic database outage")

        event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
        try:
            broken = await clients[0].get("/api/health/ready")
            assert broken.status_code == 503
            assert broken.json()["checks"]["database"] == "unavailable"
        finally:
            event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)
        app.state.settings.READINESS_REQUIRED_COMPONENTS = ["database"]
        app.state.background_queue_service.queue_manager.dependency_worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await app.state.background_queue_service.queue_manager.dependency_worker
        response = await clients[0].get("/api/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["critical_services"] == "unavailable"
    finally:
        await app.state.background_queue_service.stop()
        await supervisor.shutdown()
    app.state.settings.RECORDING_DIRECTORY = str(root / "not-created")
    response = await clients[0].get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["recordings_path"] == "unavailable"
    assert not (root / "not-created").exists()
