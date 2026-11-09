"""Default app.main compatibility provider still honors its runtime storage context."""

import pytest

from app import dependencies
from app.config import settings as settings_module
from app.config.settings import Settings
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_default_recording_provider_honors_configured_storage(
    tmp_path, monkeypatch
):
    settings = Settings(
        ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path / "owned"), _env_file=None
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(dependencies, "recording_manager", None)
    manager = await run_in_thread_pool(dependencies.get_recording_manager)
    assert (
        manager.orchestrator.config_manager.get_output_directory()
        == settings.RECORDING_DIRECTORY
    )
    assert await run_in_thread_pool(dependencies.get_recording_manager) is manager
