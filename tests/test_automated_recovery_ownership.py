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
