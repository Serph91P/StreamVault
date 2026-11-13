"""Background startup must not replace or stop another context's supervisor."""

import asyncio
from types import SimpleNamespace
import sys

import pytest

import importlib
from app.services.system.supervisor import TaskSupervisor

startup_init = importlib.import_module("app.services.init.startup_init")


@pytest.mark.asyncio
async def test_explicit_startup_supervisor_does_not_replace_or_stop_the_legacy_owner(
    monkeypatch,
) -> None:
    own = TaskSupervisor("test-own-background")
    peer = TaskSupervisor("test-peer-background")
    own_closed, peer_closed = asyncio.Event(), asyncio.Event()

    async def waiting(closed):
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()

    own_task = own.create_task("own-work", waiting(own_closed))
    peer_task = peer.create_task("peer-work", waiting(peer_closed))
    await asyncio.sleep(0)

    async def external_service(*_args, **_kwargs):
        return True

    # Keep provider/image/recovery effects outside this supervisor wiring test.
    for name in (
        "initialize_vapid_keys",
        "initialize_background_queue_with_fixes",
        "verify_queue_readiness",
        "recover_active_recordings",
        "unified_recovery_scan",
        "initialize_image_sync_service",
        "start_session_cleanup_service",
        "start_zombie_recording_cleanup_service",
        "shutdown_background_queue",
    ):
        monkeypatch.setattr(startup_init, name, external_service)
    monkeypatch.setitem(
        sys.modules,
        "app.services.images.auto_image_sync_service",
        SimpleNamespace(
            auto_image_sync_service=SimpleNamespace(stop_sync_worker=external_service)
        ),
    )
    monkeypatch.setattr(startup_init, "_background_supervisor", peer)
    try:
        await startup_init.initialize_background_services(supervisor=own)
        assert startup_init._background_supervisor is peer
        await startup_init.shutdown_background_services(supervisor=own)
        assert own_task.done() and own_closed.is_set()
        assert not peer_task.done() and not peer_closed.is_set()
        assert startup_init._background_supervisor is peer
        await startup_init.shutdown_background_services()
        assert peer_task.done() and peer_closed.is_set()
        assert startup_init._background_supervisor is None
    finally:
        await own.shutdown()
        await peer.shutdown()
