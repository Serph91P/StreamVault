"""Lifecycle defensive paths never admit a recording or block the owner loop.

Value: protects=absent process-manager/streamer/capture file degrade to a clean
False/None without a child, peer effect, or false success;
fails_when=a missing manager is treated as a started/stopped process, or a missing
streamer/file manufactures a success;
why_new=existing lifecycle tables cover real children, refusal, and admission, not
these no-manager/missing-identity guards;
seam=none; no_claim=provider capture or media completion.
"""

from pathlib import Path

import pytest
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
async def test_lifecycle_missing_manager_and_identity_guards_degrade_cleanly(
    image_applications,
):
    apps, databases, _clients, _ = image_applications
    app = apps[0]
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    saved = lifecycle.process_manager
    try:
        assert lifecycle._completion_file_size(None) is None
        assert (
            await run_in_thread_pool(
                lifecycle._completion_file_size,
                str(Path(app.state.settings.RECORDING_DIRECTORY) / "absent.ts"),
            )
            is None
        )
        lifecycle.process_manager = None
        assert await lifecycle._start_recording_process(1, "/tmp/never.ts", 1) is False
        assert await lifecycle._stop_recording_process(1) is False
        assert await lifecycle._check_recording_process(1) is False
    finally:
        lifecycle.process_manager = saved
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
