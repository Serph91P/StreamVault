"""Background preparation reports already-bootstrapped app VAPID state only."""

import importlib
import logging
from secrets import token_urlsafe
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config.settings import Settings
from app.services.system.supervisor import TaskSupervisor


@pytest.mark.asyncio
@pytest.mark.parametrize("ready", [False, True])
async def test_background_startup_uses_only_explicit_vapid_state(
    ready, monkeypatch, caplog
):
    startup = importlib.import_module("app.services.init.startup_init")
    config = importlib.import_module("app.config.settings")
    own = Settings(
        ENVIRONMENT="test",
        _env_file=None,
        VAPID_PUBLIC_KEY="synthetic-app-public" if ready else None,
        VAPID_PRIVATE_KEY=SecretStr(token_urlsafe(32)) if ready else None,
    )
    global_reads = []

    def foreign_keys():
        global_reads.append(True)
        raise AssertionError("Foreign VAPID settings read")

    monkeypatch.setattr(
        config, "settings", SimpleNamespace(get_vapid_keys=foreign_keys)
    )

    async def external(*args, **kwargs):
        return False

    for name in (
        "initialize_background_queue_with_fixes",
        "verify_queue_readiness",
        "initialize_image_sync_service",
        "start_session_cleanup_service",
        "start_zombie_recording_cleanup_service",
    ):
        monkeypatch.setattr(startup, name, external)
    before = own.get_vapid_keys()
    supervisor = TaskSupervisor("test-own-vapid")
    try:
        with caplog.at_level(logging.INFO, logger="streamvault"):
            await startup.initialize_background_services(
                supervisor=supervisor, settings=own
            )
        assert global_reads == []
        assert ("VAPID keys initialized successfully" in caplog.text) is ready
        assert ("VAPID keys could not be initialized" in caplog.text) is not ready
        assert own.get_vapid_keys() == before
    finally:
        await supervisor.shutdown()
