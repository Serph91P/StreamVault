"""Mounted recovery controls and their owned child must not cross application lifetimes."""

import asyncio

import pytest

from app.api import automated_recovery_endpoints as recovery
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
async def test_recovery_configuration_and_statistics_are_application_owned(
    proxy_applications, monkeypatch
):
    _, _, clients, _ = proxy_applications
    monkeypatch.setattr(recovery, "recovery_state", recovery.AutomatedRecoveryState())
    before = await clients[1].get("/api/recovery/automated/status")
    assert before.status_code == 200
    changed = await clients[0].post(
        "/api/recovery/automated/configure", params={"interval_minutes": 23}
    )
    assert changed.status_code == 200
    assert changed.json()["current_config"]["interval_minutes"] == 23
    own = await clients[0].get("/api/recovery/automated/status")
    peer = await clients[1].get("/api/recovery/automated/status")
    assert own.json()["data"]["interval_minutes"] == 23
    assert peer.json() == before.json()


@pytest.mark.asyncio
async def test_recovery_stop_awaits_owned_child_cleanup():
    state = recovery.AutomatedRecoveryState()
    entered, draining, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def child():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            draining.set()
            await release.wait()

    task = asyncio.create_task(child())
    await state.set_task(task)
    await entered.wait()
    stop = asyncio.create_task(state.cancel_task())
    try:
        await asyncio.wait_for(draining.wait(), 1)
        assert not stop.done(), (
            "stop reported completion before the owned child drained"
        )
        release.set()
        await stop
        assert task.done()
        assert await state.get_task() is None
    finally:
        release.set()
        await asyncio.gather(stop, task, return_exceptions=True)


@pytest.mark.asyncio
async def test_recovery_stop_retains_child_through_repeated_caller_cancellation():
    state = recovery.AutomatedRecoveryState()
    entered, draining, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def child():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            draining.set()
            await release.wait()

    task = asyncio.create_task(child())
    await state.set_task(task)
    await entered.wait()
    stop = asyncio.create_task(state.cancel_task())
    try:
        await asyncio.wait_for(draining.wait(), 1)
        for _ in range(2):
            stop.cancel()
            await asyncio.sleep(0)
            assert not stop.done() and not task.done()
            assert await state.get_task() is task
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await stop
        assert task.done()
        assert await state.get_task() is None
    finally:
        release.set()
        await asyncio.gather(stop, task, return_exceptions=True)


@pytest.mark.asyncio
async def test_parallel_starts_own_one_named_child_and_stop_preserves_peer(
    proxy_applications, monkeypatch
):
    applications, _, clients, _ = proxy_applications
    supervisors = [
        recovery.TaskSupervisor(f"recovery-test-{index}") for index in range(2)
    ]
    entered = [asyncio.Event(), asyncio.Event()]

    async def held_scan(*, state, service=None):
        index = next(
            index
            for index, app in enumerate(applications)
            if app.state.automated_recovery_state is state
        )
        await state.increment_total_runs()
        entered[index].set()
        await asyncio.Event().wait()

    monkeypatch.setattr(recovery, "run_comprehensive_recovery", held_scan)
    for app, supervisor in zip(applications, supervisors, strict=True):
        app.state.task_supervisor = supervisor
    try:
        starts = await asyncio.gather(
            *(clients[0].post("/api/recovery/automated/start") for _ in range(8))
        )
        assert all(response.status_code == 200 for response in starts)
        assert sum(response.json()["success"] for response in starts) == 1
        peer = await clients[1].post("/api/recovery/automated/start")
        assert peer.status_code == 200 and peer.json()["success"] is True
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered)), 1)
        tasks = [
            await app.state.automated_recovery_state.get_task() for app in applications
        ]
        assert tasks[0] is not tasks[1]
        for index, task in enumerate(tasks):
            assert (
                task.get_name()
                == f"streamvault:recovery-test-{index}:automated-recovery"
            )
        stopped = await clients[0].post("/api/recovery/automated/stop")
        assert stopped.status_code == 200 and stopped.json()["success"] is True
        assert tasks[0].done() and not tasks[1].done()
        assert await applications[1].state.automated_recovery_state.is_running()
        status = await clients[1].get("/api/recovery/automated/status")
        assert status.json()["data"]["statistics"]["total_runs"] == 1
    finally:
        for app in applications:
            await app.state.automated_recovery_state.cancel_task()
        for supervisor in supervisors:
            await supervisor.shutdown()


@pytest.mark.asyncio
async def test_manual_simple_recovery_uses_owned_scanner_not_default_catalogue(
    proxy_applications, monkeypatch
):
    applications, _, clients, queries = proxy_applications
    from app.services.recording import unified_recovery_service

    async def forbidden_default():
        raise AssertionError("default catalogue must not be consulted")

    monkeypatch.setattr(
        unified_recovery_service, "get_unified_recovery_service", forbidden_default
    )
    queries.clear()
    result = await clients[0].post("/api/recovery/automated/run-simple")
    assert result.status_code == 200
    assert result.json()["success"] is True
    assert result.json()["total_recoveries"] == 0
    peer = await clients[1].get("/api/recovery/automated/status")
    assert peer.json()["data"]["statistics"]["total_runs"] == 0


@pytest.mark.asyncio
async def test_nonempty_simple_recovery_admits_only_owned_journal_chain_off_loop(
    proxy_applications, monkeypatch
):
    from datetime import datetime, timezone
    from pathlib import Path
    from threading import get_ident
    from app import database as database_module
    from app.models import BackgroundTask, Recording, Stream

    applications, databases, clients, queries = proxy_applications
    files = [
        Path(app.state.settings.RECORDING_DIRECTORY) / "recovery.ts"
        for app in applications
    ]
    for index, database in enumerate(databases):
        files[index].write_bytes(bytes([index + 1]) * 2048)
        with database.sync_session_factory() as session:
            session.add(Stream(id=71, streamer_id=1, title=f"recovery-owner-{index}"))
            session.flush()
            session.add(
                Recording(
                    id=72,
                    stream_id=71,
                    status="completed",
                    start_time=datetime.now(timezone.utc),
                    path=str(files[index]),
                )
            )
            session.commit()

    def forbidden_default():
        raise AssertionError("simple chain borrowed the default catalogue")

    observed = []
    native_stat = Path.stat

    def stat(path, *args, **kwargs):
        if path in files:
            observed.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(database_module, "SessionLocal", forbidden_default)
    monkeypatch.setattr(Path, "stat", stat)
    queries.clear()
    result = await clients[0].post("/api/recovery/automated/run-simple")
    assert result.status_code == 200, result.text
    assert result.json()["success"] is True
    assert result.json()["total_recoveries"] == 1
    request_queries = list(queries)
    request_stats = list(observed)
    with databases[0].sync_session_factory() as session:
        tasks = session.query(BackgroundTask).all()
        assert len(tasks) == 6
        assert {task.task_type for task in tasks} == {
            "metadata_generation",
            "chapters_generation",
            "mp4_remux",
            "mp4_validation",
            "thumbnail_generation",
            "cleanup",
        }
        assert all(
            task.payload["recording_id"] == 72 and task.payload["stream_id"] == 71
            for task in tasks
        )
    with databases[1].sync_session_factory() as session:
        assert session.query(BackgroundTask).count() == 0
        assert session.get(Recording, 72).status == "completed"
    assert request_queries and all(
        thread != get_ident() for thread, _ in request_queries
    )
    assert request_stats and get_ident() not in request_stats
    assert files[0].read_bytes() == bytes([1]) * 2048
    assert files[1].read_bytes() == bytes([2]) * 2048


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["run-once", "test-services"])
async def test_comprehensive_and_diagnostic_scans_use_owned_services(
    proxy_applications, monkeypatch, path
):
    from app.services.recording import (
        unified_recovery_service,
        orphaned_recovery_service,
    )
    from threading import get_ident

    _, _, clients, queries = proxy_applications

    async def forbidden_default():
        raise AssertionError("automated recovery borrowed a global service")

    monkeypatch.setattr(
        unified_recovery_service, "get_unified_recovery_service", forbidden_default
    )
    monkeypatch.setattr(
        orphaned_recovery_service, "get_orphaned_recovery_service", forbidden_default
    )
    queries.clear()
    response = await (clients[0].post if path == "run-once" else clients[0].get)(
        f"/api/recovery/automated/{path}"
    )
    assert response.status_code == 200
    result = response.json()
    if path == "run-once":
        assert result["unified_recovery"]["success"] is True
        assert result["orphaned_recovery"]["success"] is True
        assert result["failed_recovery"]["success"] is True
    else:
        assert result["services"]["unified_recovery"]["available"] is True
        assert result["services"]["orphaned_recovery"]["available"] is True
        assert result["services"]["failed_recovery"]["available"] is True
    assert queries and all(thread != get_ident() for thread, _ in queries)


@pytest.mark.asyncio
async def test_recovery_activity_log_uses_owned_directory_off_loop(
    proxy_applications, monkeypatch
):
    import builtins
    from pathlib import Path
    from threading import get_ident

    applications, _, clients, _ = proxy_applications
    roots = [
        Path(app.state.settings.RECORDING_DIRECTORY) / "logs" for app in applications
    ]
    for app, root in zip(applications, roots, strict=True):
        app.state.settings.LOGS_BASE_DIR = str(root)
    opened = []
    native_open = builtins.open

    def observed_open(path, *args, **kwargs):
        if isinstance(path, (str, Path)) and any(
            Path(path).is_relative_to(root) for root in roots
        ):
            opened.append(get_ident())
        return native_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", observed_open)
    response = await clients[0].post("/api/recovery/automated/run-simple")
    assert response.status_code == 200 and response.json()["success"] is True
    request_opens = list(opened)
    assert any(
        "SYSTEM_RECOVERY" in path.read_text() for path in roots[0].rglob("*.log")
    )
    assert not any(
        "SYSTEM_RECOVERY" in path.read_text() for path in roots[1].rglob("*.log")
    )
    assert request_opens and get_ident() not in request_opens


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["run-simple", "run-once", "test-services"])
async def test_owned_scan_database_fault_cannot_be_successful_or_poison_peer(
    proxy_applications, path
):
    from sqlalchemy import event

    _, databases, clients, _ = proxy_applications

    def fault(_, __, statement, *___):
        if "FROM recordings" in statement:
            raise RuntimeError("synthetic-secret-token catalogue unavailable")

    event.listen(databases[0].sync_engine, "before_cursor_execute", fault)
    response = await (clients[0].get if path == "test-services" else clients[0].post)(
        f"/api/recovery/automated/{path}"
    )
    assert response.status_code == 200
    result = response.json()
    if path == "run-simple":
        assert result["success"] is False
        status = await clients[0].get("/api/recovery/automated/status")
        assert status.json()["data"]["statistics"]["failed_runs"] == 1
        assert status.json()["data"]["statistics"]["successful_runs"] == 0
    elif path == "run-once":
        assert result["success"] is False
        assert result["unified_recovery"]["success"] is False
        assert result["orphaned_recovery"]["success"] is False
        assert result["failed_recovery"]["success"] is False
    else:
        assert result["services"]["unified_recovery"]["available"] is False
        assert result["services"]["orphaned_recovery"]["available"] is False
    assert "synthetic-secret-token" not in response.text
    peer = await clients[1].post("/api/recovery/automated/run-simple")
    assert peer.status_code == 200 and peer.json()["success"] is True
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)
