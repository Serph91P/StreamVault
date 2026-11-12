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
from app.models import BackgroundTask, Recording, Stream, StreamEvent
from app.services.queues.task_progress_tracker import TaskStatus
from app.utils.retry_decorator import NonRetryableError
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "finish,admission",
    [
        ("active", "catalog"),
        ("completed", "catalog"),
        ("missing", "catalog"),
        ("error", "catalog"),
        ("database-failed", "catalog"),
        ("active", "force-new"),
        ("active", "force-existing"),
        ("manual-stop", "catalog"),
        ("automatic-stop", "catalog"),
        ("progress", "catalog"),
        ("duplicate", "catalog"),
        ("shutdown", "catalog"),
        ("removed-before-process", "catalog"),
        ("monitor-completion", "catalog"),
    ],
)
async def test_recording_start_keeps_external_task_and_sql_with_the_application_owner(
    image_applications, monkeypatch, finish, admission
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    if admission != "catalog":
        app.state.settings.TWITCH_APP_ID = "local-owner-control"
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
                    id=69 if admission == "force-new" else 70,
                    streamer_id=1,
                    title="Local child contract",
                    started_at=now,
                    twitch_stream_id="previous"
                    if admission == "force-new"
                    else "local-live-70",
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
        if finish == "monitor-completion":
            lifecycle.process_manager.active_processes["stream_70"] = child
        return child

    # The media-provider port is a real controlled OS child. Isolate its separate
    # polling contract so this test does not claim ProcessManager/media recovery.
    async def hold_monitor(_recording_id):
        await asyncio.Event().wait()

    monkeypatch.setattr(lifecycle.process_manager, "start_recording_process", spawn)
    native_monitor = lifecycle.monitor_and_process_recording
    monitor_observed = asyncio.Event()
    if finish == "monitor-completion":
        native_progress = lifecycle._update_recording_progress

        async def observed_progress(identity):
            result = await native_progress(identity)
            monitor_observed.set()
            return result

        monkeypatch.setattr(lifecycle, "_update_recording_progress", observed_progress)
    else:
        monkeypatch.setattr(lifecycle, "monitor_and_process_recording", hold_monitor)
    if finish == "removed-before-process":
        native_create = lifecycle.database_service.create_recording

        async def removed_after_create(*args, **kwargs):
            value = await native_create(*args, **kwargs)

            def remove():
                with database.sync_session_factory() as db:
                    db.delete(db.get(Recording, value.id))
                    db.commit()

            await run_in_thread_pool(remove)
            return value

        monkeypatch.setattr(
            lifecycle.database_service, "create_recording", removed_after_create
        )
    rejected = []

    def denied_update(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("UPDATE RECORDINGS ") and not rejected:
            rejected.append(True)
            raise NonRetryableError("synthetic-completion-update-denied")

    runner = None
    try:
        if admission == "catalog":
            recording_id = await manager.orchestrator.start_recording(70, 999)
        else:
            from aiohttp import web

            async def streams(request):
                assert request.query["user_id"] == "owner-0"
                assert request.headers["Client-ID"] == "local-owner-control"
                assert database.sync_engine.pool.checkedout() == 0
                return web.json_response(
                    {
                        "data": [
                            {
                                "id": "local-live-70",
                                "title": "Local child contract",
                                "game_name": "Synthetic category",
                                "language": "en",
                            }
                        ]
                    }
                )

            provider = web.Application()
            provider.router.add_get("/helix/streams", streams)
            runner = web.AppRunner(provider)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            api = lifecycle._twitch_api_service
            api.base_url = f"http://127.0.0.1:{runner.addresses[0][1]}/helix"
            api._access_token = "synthetic-local-control"
            api._token_expires_at = float("inf")
            recording_id = await lifecycle.force_start_recording(1)
        if finish == "removed-before-process":
            assert recording_id is None
            assert children == []
            assert app.state.background_queue_service.external_tasks == {}
            assert not lifecycle.state_manager.get_active_recordings()
            assert not peer.external_tasks
            assert sql_threads and loop_thread not in sql_threads
            assert database.sync_engine.pool.checkedout() == 0
            return
        assert recording_id is not None
        production_sql_threads = list(sql_threads)
        event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
        with database.sync_session_factory() as db:
            recording = db.get(Recording, recording_id)
            path = Path(recording.path)
            if admission != "catalog":
                assert recording.stream_id == 70
                assert (
                    db.query(Stream).filter_by(twitch_stream_id="local-live-70").count()
                    == 1
                )
                assert db.query(StreamEvent).filter_by(stream_id=70).count() > 0
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
        if finish == "monitor-completion":
            from app.config.constants import ASYNC_DELAYS

            await asyncio.wait_for(monitor_observed.wait(), 5)
            children[0].terminate()
            await children[0].wait()
            lifecycle.process_manager.active_processes.pop("stream_70")

            async def completed():
                while lifecycle.state_manager.get_active_recording(recording_id):
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(
                completed(), ASYNC_DELAYS.RECORDING_MONITOR_INTERVAL + 5
            )
            with database.sync_session_factory() as db:
                assert db.get(Recording, recording_id).status == "completed"
            assert task.status is TaskStatus.COMPLETED
            await manager.shutdown()
            with database.sync_session_factory() as db:
                assert db.query(BackgroundTask).count() > 0
        elif finish in {"duplicate", "shutdown"}:
            lifecycle.process_manager.active_processes["stream_70"] = children[0]
            if finish == "shutdown":
                await manager.shutdown()
                assert children[0].returncode is not None
            event.listen(database.sync_engine, "before_cursor_execute", observe_sql)
            assert await lifecycle.start_recording(70, 1) is None
            assert len(children) == 1
            if finish == "duplicate":
                await asyncio.wait_for(native_monitor(999), 3)
                assert 999 not in lifecycle.state_manager.get_active_tasks()
            assert loop_thread not in sql_threads
            event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
            with database.sync_session_factory() as db:
                assert db.query(Recording).count() == 1
        elif finish == "progress":
            lifecycle.process_manager.active_processes["stream_70"] = children[0]
            event.listen(database.sync_engine, "before_cursor_execute", observe_sql)
            progress = await lifecycle.process_manager.get_recording_progress(
                recording_id
            )
            assert progress is not None and progress["status"] == "running"
            assert progress["pid"] == children[0].pid
            children[0].terminate()
            await children[0].wait()
            assert await lifecycle.process_manager.get_recording_progress(
                recording_id
            ) == {"status": "completed", "exit_code": children[0].returncode}
            await lifecycle._update_recording_progress(recording_id)
            assert task.progress == 100
            assert (
                lifecycle.state_manager.get_active_recording(recording_id)["progress"]
                == 100
            )
            assert await lifecycle.process_manager.get_recording_progress(999) is None
            assert loop_thread not in sql_threads
            event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
        elif finish in {"manual-stop", "automatic-stop"}:
            lifecycle.process_manager.active_processes["stream_70"] = children[0]
            event.listen(database.sync_engine, "before_cursor_execute", observe_sql)
            reason = "automatic" if finish == "automatic-stop" else "manual"
            assert await lifecycle.stop_recording(recording_id, reason=reason) is True
            assert children[0].returncode is not None
            assert not lifecycle.state_manager.get_active_recordings()
            assert "stream_70" not in lifecycle.process_manager.active_processes
            assert loop_thread not in sql_threads
            event.remove(database.sync_engine, "before_cursor_execute", observe_sql)
            with database.sync_session_factory() as db:
                assert db.get(Recording, recording_id).status == "stopped"
            assert await lifecycle.stop_recording(recording_id, reason=reason) is False
            assert not peer.external_tasks
            if finish == "automatic-stop":
                await manager.shutdown()
                with database.sync_session_factory() as db:
                    assert db.query(BackgroundTask).count() > 0
        elif finish != "active":
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
        # Defensive cleanup of only this fixture's coroutine if an assertion
        # fails; the completed case above independently proves owner shutdown.
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
        if runner is not None:
            await runner.cleanup()
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
