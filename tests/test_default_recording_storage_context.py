"""Default app.main compatibility resolves its initialized app-owned recorder."""

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
async def test_default_recording_provider_honors_configured_storage(
    image_applications, monkeypatch
):
    apps, _, _, _ = image_applications
    with monkeypatch.context() as legacy:
        legacy.setattr(dependencies, "recording_manager", None)
        legacy.setattr(apps[0].state, "legacy_default", True)
        owner = await run_in_thread_pool(
            dependencies.get_lifespan_service(
                apps[0], dependencies.get_recording_manager
            )
        )
        peer = await run_in_thread_pool(
            dependencies.get_application_recording_manager,
            HTTPConnection({"type": "http", "app": apps[1], "headers": []}),
        )
        assert (
            owner.orchestrator.config_manager.get_output_directory()
            == apps[0].state.settings.RECORDING_DIRECTORY
        )
        assert (
            peer.orchestrator.config_manager.get_output_directory()
            == apps[1].state.settings.RECORDING_DIRECTORY
        )
        assert peer is not owner
        assert await run_in_thread_pool(dependencies.get_recording_manager) is owner
        assert (
            await run_in_thread_pool(
                dependencies.get_application_recording_manager,
                HTTPConnection({"type": "http", "app": apps[0], "headers": []}),
            )
            is owner
        )
