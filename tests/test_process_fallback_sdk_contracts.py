"""Retained no-callback SDK fallback against real closed DAO values and queue.

The legacy default getter is bound to an isolated real application, not a fake
result. This is not proof the normal application should use this fallback.
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import BackgroundTask, Recording, Stream, Streamer
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "explicit",
        "discover",
        "legacy-path-mismatch",
        "missing-recording",
        "missing-stream",
    ],
)
async def test_native_legacy_process_fallback_uses_recording_identity_and_persists_admission(
    image_applications, monkeypatch, mode
):
    import importlib

    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]
    for owner in apps:
        monkeypatch.setattr(
            owner.state.settings,
            "LOGS_BASE_DIR",
            owner.state.settings.RECORDING_DIRECTORY + "/.logs",
        )

    def seed():
        with database.sync_session_factory() as db:
            username = db.get(Streamer, 1).username
            output = (
                Path(app.state.settings.RECORDING_DIRECTORY)
                / (username if mode != "legacy-path-mismatch" else "unmatched-folder")
                / "capture.ts"
            )
            output.parent.mkdir()
            with output.open("wb") as file:
                file.truncate(2 * 1024 * 1024)
            db.add(Stream(id=70, streamer_id=1, title="SDK retained fallback"))
            db.flush()
            db.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="recording",
                    path=str(output),
                    start_time=datetime.now(timezone.utc),
                )
            )
            db.commit()
            return str(output)

    output = await run_in_thread_pool(seed)
    recorder = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app}),
    )
    monkeypatch.setattr(
        importlib.import_module("app.routes.recording"),
        "get_recording_service",
        lambda: recorder._service,
    )
    threads = []

    def sql(*_args):
        threads.append(get_ident())

    event.listen(database.sync_engine, "before_cursor_execute", sql)
    try:
        identity = (
            999 if mode == "missing-recording" else 7 if mode == "explicit" else None
        )
        stream_id = 999 if mode == "missing-stream" else 70
        await recorder.process_manager._fallback_trigger_post_processing(
            stream_id, output, recording_id=identity
        )
        assert threads and get_ident() not in threads
        event.remove(database.sync_engine, "before_cursor_execute", sql)
        expected = mode not in {"missing-recording", "missing-stream"}
        with database.sync_session_factory() as db:
            recording = db.get(Recording, 7)
            assert recording.status == ("completed" if expected else "recording")
            assert recording.path == output
            tasks = db.query(BackgroundTask).all()
            assert bool(tasks) is expected
            if tasks:
                assert all(
                    task.payload["recording_id"] == 7
                    and task.payload["stream_id"] == 70
                    for task in tasks
                )
        with databases[1].sync_session_factory() as db:
            assert db.query(Recording).count() == 0
            assert db.query(BackgroundTask).count() == 0
        assert Path(output).stat().st_size == 2 * 1024 * 1024
    finally:
        if event.contains(database.sync_engine, "before_cursor_execute", sql):
            event.remove(database.sync_engine, "before_cursor_execute", sql)
        await close_owned(apps)
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)
