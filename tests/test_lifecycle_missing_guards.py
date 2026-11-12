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


@pytest.mark.asyncio
async def test_lifecycle_error_and_completion_failures_do_not_manufacture_success(
    image_applications, monkeypatch
):
    """Database/notification faults surface as a failed recording, never a success.

    Value: protects=an error handler whose persistence fails still clears the ghost
    active entry and does not emit a false completion;
    fails_when=the failure is swallowed into a success status or the ghost stays active;
    why_new=positive error/completion rows cover the happy path, not the fault path;
    seam=none; no_claim=provider capture or media completion.
    """
    from datetime import datetime, timezone

    from app.models import Recording, Stream

    apps, databases, _clients, _ = image_applications
    app = apps[0]
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    database = databases[0]

    def seed():
        with database.sync_session_factory() as db:
            db.add(Stream(id=72, streamer_id=1, title="fault owner"))
            db.flush()
            db.add(
                Recording(
                    id=11,
                    stream_id=72,
                    status="recording",
                    start_time=datetime.now(timezone.utc),
                )
            )
            db.commit()

    await run_in_thread_pool(seed)
    lifecycle.state_manager.add_active_recording(
        11, {"file_path": "/absent/never.ts", "streamer_id": 1, "stream_id": 72}
    )

    async def raising_mark_failed(*_args, **_kwargs):
        raise RuntimeError("synthetic mark-failed denial")

    monkeypatch.setattr(
        lifecycle.database_service, "mark_recording_failed", raising_mark_failed
    )
    try:
        await lifecycle._handle_recording_error(11, "synthetic error")
        assert lifecycle.state_manager.get_active_recording(11) is None
        await lifecycle._handle_recording_completion(11)
    finally:
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
