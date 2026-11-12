"""Real recording catalogue/path/child ports; not a provider/media canary."""

import asyncio
from datetime import datetime, timezone
import importlib
import os
from pathlib import Path
import sys
import threading

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import Recording, Stream
from app.services.queues.task_progress_tracker import TaskStatus
from app.utils.retry_decorator import NonRetryableError
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "finish", ["active", "completed", "missing", "error", "database-failed"]
)
async def test_recording_start_keeps_external_task_and_sql_with_the_application_owner(
    image_applications, monkeypatch, finish
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
    rejected = []

    def denied_update(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("UPDATE RECORDINGS ") and not rejected:
            rejected.append(True)
            raise NonRetryableError("synthetic-completion-update-denied")

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
        if finish != "active":
            for child in children:
                child.terminate()
                await child.wait()
            if finish == "missing":
                path.unlink()
            io_threads = []
            native_stat = os.stat

            def stat(candidate, *args, **kwargs):
                if isinstance(candidate, (str, bytes, os.PathLike)) and os.fsdecode(
                    candidate
                ) == str(path):
                    io_threads.append(threading.get_ident())
                return native_stat(candidate, *args, **kwargs)

            monkeypatch.setattr(os, "stat", stat)
            if finish == "database-failed":
                event.listen(
                    database.sync_engine, "before_cursor_execute", denied_update
                )
            if finish == "error":
                await lifecycle._handle_recording_error(
                    recording_id, "synthetic-owned-child-error"
                )
            else:
                await lifecycle._handle_recording_completion(recording_id)
            assert {
                "event_loop_file_io": loop_thread in io_threads,
                "task_failed": task.status is TaskStatus.FAILED,
            } == {"event_loop_file_io": False, "task_failed": finish != "completed"}
            assert not lifecycle.state_manager.get_active_recordings()
            assert not peer.external_tasks
            with database.sync_session_factory() as db:
                assert db.get(Recording, recording_id).status == (
                    "completed" if finish == "completed" else "failed"
                )
            await lifecycle._handle_recording_completion(recording_id)
            assert (task.status is TaskStatus.FAILED) is (finish != "completed")
            if finish == "completed":
                pending = []
                for candidate in asyncio.all_tasks():
                    coroutine = candidate.get_coro()
                    frame = getattr(coroutine, "cr_frame", None)
                    if (
                        frame is not None
                        and frame.f_locals.get("self") is lifecycle
                        and getattr(coroutine, "__qualname__", "").endswith(
                            "._trigger_post_processing_async"
                        )
                    ):
                        pending.append(candidate)
                assert pending
                await manager.shutdown()
                assert all(candidate.done() for candidate in pending), (
                    "Owner shutdown left its fallback running"
                )
                assert loop_thread not in io_threads
                from app.models import BackgroundTask

                with database.sync_session_factory() as db:
                    assert db.query(BackgroundTask).count() > 0
    finally:
        if event.contains(database.sync_engine, "before_cursor_execute", denied_update):
            event.remove(database.sync_engine, "before_cursor_execute", denied_update)
        if event.contains(database.sync_engine, "before_cursor_execute", observe_sql):
            event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
        tasks = list(lifecycle.state_manager.get_active_tasks().values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # Cleanup only this test's legacy fallback coroutine; this is not a
        # claim that the current production shutdown already owns that task.
        fallback_tasks = []
        for candidate in asyncio.all_tasks():
            coroutine = candidate.get_coro()
            frame = getattr(coroutine, "cr_frame", None)
            if (
                frame is not None
                and frame.f_locals.get("self") is lifecycle
                and getattr(coroutine, "__qualname__", "").endswith(
                    "._trigger_post_processing_async"
                )
            ):
                fallback_tasks.append(candidate)
                candidate.cancel()
        await asyncio.gather(*fallback_tasks, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.terminate()
            await child.wait()
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
