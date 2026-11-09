"""Mounted health endpoints must probe and authorize only their own application."""

import importlib
from threading import get_ident

import pytest
from pydantic import SecretStr
from sqlalchemy import event

import test_logging_application_ownership

image_applications = test_logging_application_ownership.image_applications


@pytest.mark.asyncio
async def test_readiness_command_repeated_cancellation_awaits_native_child_reaping(
    tmp_path, monkeypatch
):
    import asyncio
    import sys

    health = importlib.import_module("app.routes.health")
    command = tmp_path / "health-probe"
    command.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(60)\n")
    command.chmod(0o700)
    spawned, cleanup_entered, release = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )
    native_spawn = asyncio.create_subprocess_exec
    processes = []
    original_waits = []

    async def spawn(*args, **kwargs):
        process = await native_spawn(*args, **kwargs)
        processes.append(process)
        original = process.wait
        original_waits.append(original)
        waits = 0

        async def wait():
            nonlocal waits
            waits += 1
            if waits >= 2:
                cleanup_entered.set()
                await release.wait()
            return await original()

        monkeypatch.setattr(process, "wait", wait)
        spawned.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    task = asyncio.create_task(health._check_command(str(command)))
    try:
        await asyncio.wait_for(spawned.wait(), 2)
        task.cancel()
        await asyncio.wait_for(cleanup_entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not task.done(), "repeated cancellation abandoned native child reaping"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert processes[0].returncode is not None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        for process, wait in zip(processes, original_waits, strict=True):
            if process.returncode is None:
                process.kill()
            await wait()


@pytest.mark.asyncio
async def test_health_and_readiness_use_owned_catalogue_and_policy(
    image_applications, monkeypatch
):
    apps, databases, clients, queries = image_applications
    health = importlib.import_module("app.routes.health")
    defaults = []

    def forbidden():
        defaults.append(True)
        raise AssertionError("health borrowed default catalogue")

    monkeypatch.setattr(health, "SessionLocal", forbidden)
    apps[0].state.settings.READINESS_REQUIRED_COMPONENTS = ["database"]
    apps[1].state.settings.READINESS_REQUIRED_COMPONENTS = ["synthetic-unknown"]
    for client in clients:
        queries.clear()
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["checks"]["database"] == "healthy"
        assert queries and get_ident() not in [thread for thread, _ in queries]
    first = await clients[0].get("/api/health/ready")
    assert first.status_code == 200 and first.json()["checks"] == {"database": "ready"}
    peer = await clients[1].get("/api/health/ready")
    assert peer.status_code == 503
    assert peer.json() == {
        "status": "not_ready",
        "checks": {"synthetic-unknown": "unavailable"},
    }
    assert not defaults
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
async def test_health_database_failure_is_local_and_liveness_stays_available(
    image_applications,
):
    apps, databases, clients, _ = image_applications
    for app in apps:
        app.state.settings.READINESS_REQUIRED_COMPONENTS = ["database"]

    def unavailable(_connection, _cursor, statement, *_):
        if statement.strip() == "SELECT 1":
            raise RuntimeError("synthetic health database outage")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        assert (await clients[0].get("/api/health/ready")).status_code == 503
        assert (await clients[0].get("/api/health/live")).json() == {"status": "alive"}
        assert (await clients[1].get("/api/health/ready")).status_code == 200
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)


@pytest.mark.asyncio
async def test_metrics_enablement_and_token_belong_to_the_requesting_app(
    image_applications,
):
    apps, _, clients, _ = image_applications

    apps[0].state.settings.METRICS_ENABLED = False
    apps[1].state.settings.METRICS_ENABLED = True
    apps[1].state.settings.metrics_auth_token = SecretStr(
        "synthetic-health-scope-token"
    )
    token = {"Authorization": "Bearer synthetic-health-scope-token"}
    assert (await clients[0].get("/api/metrics", headers=token)).status_code == 404
    assert (await clients[1].get("/api/metrics")).status_code == 404
    assert (
        await clients[1].get("/api/metrics", headers={"Authorization": "Bearer wrong"})
    ).status_code == 404
    response = await clients[1].get("/api/metrics", headers=token)
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "synthetic-health-scope-token" not in response.text
