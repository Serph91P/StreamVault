"""Actual manual recording HTTP operations keep their app database and notifications."""

import importlib
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest

from tests import test_logging_application_ownership

image_applications = test_logging_application_ownership.image_applications
logging_applications = test_logging_application_ownership.logging_applications


@pytest.mark.asyncio
async def test_http_streamer_recording_settings_use_native_owner_scope(
    image_applications, monkeypatch
):
    from app.models import StreamerRecordingSettings
    from app.utils.async_db_utils import run_in_thread_pool

    _, databases, clients, queries = image_applications
    module = importlib.import_module("app.routes.recording")
    default_calls = []

    def forbidden():
        default_calls.append(True)
        raise AssertionError(
            "streamer recording settings borrowed the default catalogue"
        )

    monkeypatch.setattr(module, "SessionLocal", forbidden)

    def stored(index):
        with databases[index].sync_session_factory() as session:
            return session.query(StreamerRecordingSettings).count()

    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get("/api/recording/streamers")
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["username"] == f"owner-{index}"
        assert response.json()[0]["twitch_auth_priority"] == 0
        assert queries and get_ident() not in [thread for thread, _ in queries]
        assert await run_in_thread_pool(stored, index) == 1
        if index == 0:
            assert await run_in_thread_pool(stored, 1) == 0
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    assert not default_calls


@pytest.mark.asyncio
async def test_http_stop_reaps_only_owned_child_and_persists_only_owned_row(
    logging_applications, monkeypatch
):
    from app.models import Recording, Stream
    from app.dependencies import _get_application_recording_manager
    from app.utils.async_db_utils import run_in_thread_pool

    apps, databases, clients, _, _, _ = logging_applications
    children = []
    files = []

    def seed(index):
        file = Path(apps[index].state.settings.RECORDING_DIRECTORY) / "untouched.ts"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"synthetic source retention sentinel")
        with databases[index].sync_session_factory() as session:
            session.add(Stream(id=71, streamer_id=1, title=f"owner-{index}"))
            session.flush()
            session.add(
                Recording(
                    id=72,
                    stream_id=71,
                    start_time=datetime.now(timezone.utc),
                    status="recording",
                    path=str(file),
                )
            )
            session.commit()
        return file

    def status(index):
        with databases[index].sync_session_factory() as session:
            return session.get(Recording, 72).status

    # The event publisher is an external collaborator, not the stop/process/DB path.
    publisher = importlib.import_module(
        "app.services.recording.database_event_orphaned_recovery"
    )

    async def published(*_args, **_kwargs):
        return None

    monkeypatch.setattr(publisher, "on_recording_status_changed", published)
    try:
        for index, app in enumerate(apps):
            file = await run_in_thread_pool(seed, index)
            files.append(file)
            manager = await run_in_thread_pool(_get_application_recording_manager, app)
            service = manager._service
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import time;print('ready',flush=True);time.sleep(60)",
                stdout=asyncio.subprocess.PIPE,
            )
            children.append(child)
            assert child.stdout is not None
            assert await asyncio.wait_for(child.stdout.readline(), 3) == b"ready\n"
            service.process_manager.active_processes["stream_71"] = child
            service.orchestrator.state_manager.add_active_recording(
                72, {"streamer_id": 1, "stream_id": 71, "file_path": str(file)}
            )
        response = await clients[0].post("/api/recording/stop/1")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "status": "success",
            "message": "Recording stopped successfully",
        }
        assert children[0].returncode is not None
        assert children[1].returncode is None
        assert await run_in_thread_pool(status, 0) == "stopped"
        assert await run_in_thread_pool(status, 1) == "recording"
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        assert [file.read_bytes() for file in files] == [
            b"synthetic source retention sentinel"
        ] * 2
    finally:
        for child in children:
            if child.returncode is None:
                child.terminate()
            await child.wait()
        from app.lifespan import _close_application_proxy, _close_application_twitch

        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [("POST", "/api/recording/stop/1"), ("GET", "/api/recording/streamers")],
)
async def test_http_stop_database_fault_stays_local_and_closes_scope(
    logging_applications, method, path
):
    from sqlalchemy import event
    from app.dependencies import _get_application_recording_manager
    from app.utils.async_db_utils import run_in_thread_pool

    apps, databases, clients, _, _, _ = logging_applications
    observed = []
    for app in apps:
        await run_in_thread_pool(_get_application_recording_manager, app)

    def unavailable(_connection, _cursor, statement, *_):
        if "FROM streamers" in statement:
            observed.append(get_ident())
            raise RuntimeError("synthetic manual-stop catalogue outage")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        failed = await clients[0].request(method, path)
        peer = await clients[1].request(method, path)
        assert failed.status_code == 500
        assert failed.json() == {"detail": "Internal server error"}
        assert peer.status_code == 200
        if method == "POST":
            assert peer.json() == {
                "status": "error",
                "message": "No active recording found",
            }
        else:
            assert peer.json()[0]["username"] == "owner-1"
        assert observed and get_ident() not in observed
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)
        from app.lifespan import _close_application_proxy, _close_application_twitch

        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("streamer_id", [1, 999])
async def test_http_stop_without_capture_is_owned_and_does_not_crash(
    logging_applications, image_applications, monkeypatch, streamer_id
):
    apps, databases, clients, _, _, _ = logging_applications
    _, _, _, queries = image_applications
    module = importlib.import_module("app.routes.recording")
    default_calls = []
    notifications = []

    def default_forbidden():
        default_calls.append(True)
        raise AssertionError("manual HTTP stop borrowed default database")

    monkeypatch.setattr(module, "SessionLocal", default_forbidden)
    for index, app in enumerate(apps):
        original = app.state.websocket_manager.send_toast_notification

        async def notify(*args, index=index, original=original, **kwargs):
            notifications.append((index, kwargs))
            return await original(*args, **kwargs)

        monkeypatch.setattr(
            app.state.websocket_manager, "send_toast_notification", notify
        )
    try:
        for index, client in enumerate(clients):
            queries.clear()
            response = await client.post(f"/api/recording/stop/{streamer_id}")
            assert response.status_code == 200, response.text
            assert response.json() == {
                "status": "error",
                "message": "No active recording found",
            }
            assert notifications[-1][0] == index
            name = f"owner-{index}" if streamer_id == 1 else "Streamer 999"
            assert notifications[-1][1]["title"] == f"Stop Recording - {name}"
            assert queries and get_ident() not in [thread for thread, _ in queries]
            assert all(
                database.sync_engine.pool.checkedout() == 0 for database in databases
            )
        assert not default_calls
        assert [index for index, _ in notifications] == [0, 1]
    finally:
        from app.lifespan import _close_application_proxy, _close_application_twitch

        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)
