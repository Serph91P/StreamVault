"""Real recording catalogue/path/child ports; not a provider/media canary."""

import asyncio
from datetime import datetime, timezone
import importlib
from pathlib import Path
import sys
import threading

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
async def test_recording_start_keeps_external_task_and_sql_with_the_application_owner(
    image_applications, monkeypatch
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    now = datetime.now(timezone.utc)

    def seed():
        with database.sync_session_factory() as db:
            db.add(
                Stream(
                    id=70, streamer_id=1, title="Local child contract", started_at=now
                )
            )
            db.commit()

    await run_in_thread_pool(seed)
    loop_thread = threading.get_ident()
    sql_threads = []

    def observe_sql(*args):
        sql_threads.append(threading.get_ident())

    event.listen(database.sync_engine, "before_cursor_execute", observe_sql)
    peer = apps[1].state.background_queue_service
    monkeypatch.setattr(
        importlib.import_module("app.services.recording.recording_lifecycle_manager"),
        "background_queue_service",
        peer,
    )
    children = []

    async def spawn(**kwargs):
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import sys,time;from pathlib import Path;Path(sys.argv[1]).write_bytes(b'local lifecycle child');print('ready',flush=True);time.sleep(60)",
            kwargs["output_path"],
            stdout=asyncio.subprocess.PIPE,
        )
        children.append(child)
        assert await asyncio.wait_for(child.stdout.readline(), 5) == b"ready\n"
        return child

    # The media-provider port is a real controlled OS child. Isolate its separate
    # polling contract so this test does not claim ProcessManager/media recovery.
    async def hold_monitor(_recording_id):
        await asyncio.Event().wait()

    monkeypatch.setattr(lifecycle.process_manager, "start_recording_process", spawn)
    monkeypatch.setattr(lifecycle, "monitor_and_process_recording", hold_monitor)
    try:
        recording_id = await manager.orchestrator.start_recording(70, 999)
        assert recording_id is not None
        production_sql_threads = list(sql_threads)
        event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
        with database.sync_session_factory() as db:
            recording = db.get(Recording, recording_id)
            path = Path(recording.path)
        assert path.is_relative_to(Path(app.state.settings.RECORDING_DIRECTORY))
        assert path.read_bytes() == b"local lifecycle child"
        assert {
            "peer_tasks": len(peer.external_tasks),
            "event_loop_sql": sum(
                thread == loop_thread for thread in production_sql_threads
            ),
        } == {"peer_tasks": 0, "event_loop_sql": 0}
        task = app.state.background_queue_service.external_tasks[
            f"recording_{recording_id}"
        ]
        assert task.payload["streamer_id"] == 1 and task.payload["stream_id"] == 70
        assert production_sql_threads
    finally:
        if event.contains(database.sync_engine, "before_cursor_execute", observe_sql):
            event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
        tasks = list(lifecycle.state_manager.get_active_tasks().values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.terminate()
            await child.wait()
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
