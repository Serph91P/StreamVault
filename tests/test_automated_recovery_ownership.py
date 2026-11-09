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

    async def held_scan(*, state):
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
