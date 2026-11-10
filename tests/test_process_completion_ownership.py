"""Actual child completion must read only the recording actor's closed catalog."""

import asyncio
from datetime import datetime, timedelta, timezone
from threading import get_ident
import sys
import subprocess

from aiohttp import web
import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.dependencies import _get_application_recording_manager
from app.lifespan import _close_application_proxy, _close_application_twitch
from app.main import create_app
from app.models import GlobalSettings, Stream, StreamerRecordingSettings, Recording
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_external_notification_boundary import notification_catalogs as _catalogs

notification_catalogs = _catalogs


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [None, ""])
async def test_completion_without_a_recording_path_cannot_manufacture_notification(
    notification_catalogs, path
):
    from app.services.notifications.external_notification_service import (
        ExternalNotificationService,
    )

    database = notification_catalogs[0]
    with database.sync_session_factory() as session:
        session.add(Stream(id=7, streamer_id=1, recording_path=path))
        session.commit()
    service = ExternalNotificationService(session_factory=database.sync_session_factory)
    assert (
        await run_in_thread_pool(service._prepare_recording_completion, 7, None, None)
        is None
    )
    assert await service.send_recording_completion(7) is False
    assert await service.send_recording_completion(999) is False
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["monitor", "finalize", "failure"])
async def test_native_completion_notifies_from_closed_owned_catalogs(
    notification_catalogs, tmp_path, monkeypatch, entry
):
    databases = notification_catalogs
    received, observed = [], []
    apps, children = [], []

    async def receive(request):
        owner = int(request.match_info["owner"])
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        received.append((owner, await request.json()))
        return web.Response(status=200)

    provider = web.Application()
    provider.router.add_post("/{owner}", receive)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]

    def forbidden_default():
        raise AssertionError(
            "recording child must not borrow the process-default catalog"
        )

    monkeypatch.setattr("app.database.SessionLocal", forbidden_default)
    monkeypatch.setattr(
        "app.services.notifications.external_notification_service.SessionLocal",
        forbidden_default,
    )
    try:
        for index, database in enumerate(databases):
            root = tmp_path / f"owner-{index}"
            root.mkdir()
            recording = root / "finished.ts"
            recording.write_bytes(b"notification-size-fixture" * 1024)
            now = datetime.now(timezone.utc)
            with database.sync_session_factory() as session:
                policy = session.get(GlobalSettings, 1)
                policy.notification_url = f"json://127.0.0.1:{port}/{index}"
                policy.notify_recording_completed = True
                policy.notify_recording_failed = True
                session.add(
                    Stream(
                        id=7,
                        streamer_id=1,
                        title=f"Owner {index}",
                        started_at=now - timedelta(minutes=150 + index),
                        ended_at=now,
                        recording_path=str(recording),
                    )
                )
                session.add(
                    StreamerRecordingSettings(
                        streamer_id=1, quality=("720p", "480p")[index]
                    )
                )
                if entry == "failure":
                    session.add(
                        Recording(
                            id=8,
                            stream_id=7,
                            start_time=now,
                            status="recording",
                            path=str(recording),
                        )
                    )
                session.commit()
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(root),
                    LOGS_BASE_DIR=str(root / "logs"),
                    LOG_DIR=str(root / "logs"),
                    _env_file=None,
                ),
                database=database,
            )
            apps.append(app)
            facade = await run_in_thread_pool(_get_application_recording_manager, app)
            manager = facade._service.orchestrator.process_manager
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: observed.append(get_ident()),
            )
            if entry in {"monitor", "failure"}:
                child = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-c",
                    "import sys;sys.stderr.write('synthetic failure');sys.exit(2)"
                    if entry == "failure"
                    else "pass",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                children.append(child)
                manager.active_processes["stream_7"] = child
                expected = 2 if entry == "failure" else 0
                assert await manager.monitor_process(child) == expected
                assert child.returncode == expected
                if entry == "failure":

                    def failure_state():
                        with database.sync_session_factory() as session:
                            row = session.get(Recording, 8)
                            return (
                                row.status,
                                row.error_message,
                                row.failure_reason,
                                row.failure_timestamp,
                                row.end_time,
                            )

                    (
                        status,
                        error,
                        reason,
                        failed_at,
                        ended_at,
                    ) = await run_in_thread_pool(failure_state)
                    assert status == "failed"
                    assert (
                        error == "Streamlink exited with code 2"
                        and reason == "streamlink_crash"
                    )
                    assert failed_at is not None and ended_at is not None
                    dao = manager._get_recording_database_service()
                    assert dao is facade._service.orchestrator.database_service
                    assert (
                        await dao.mark_active_stream_recording_failed(
                            7, "must not overwrite", "later"
                        )
                        is None
                    )
                    assert (
                        await dao.mark_active_stream_recording_failed(
                            999, "absent", "absent"
                        )
                        is None
                    )
                    assert await run_in_thread_pool(failure_state) == (
                        status,
                        error,
                        reason,
                        failed_at,
                        ended_at,
                    )
            else:
                folder = root / "finished_segments"
                folder.mkdir()
                part = folder / "finished_part000.ts"
                await run_in_thread_pool(
                    subprocess.run,
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=64x64:rate=10",
                        "-t",
                        "0.3",
                        "-c:v",
                        "mpeg2video",
                        "-f",
                        "mpegts",
                        str(part),
                    ],
                    check=True,
                    capture_output=True,
                )
                admitted = []

                async def postprocessing(recording_id, path):
                    admitted.append((recording_id, path))

                manager.post_processing_callback = postprocessing
                segments = {
                    "stream_id": 7,
                    "recording_id": 8,
                    "monitor_task": None,
                    "segment_dir": str(folder),
                    "total_segments": [{"path": str(part)}],
                    "base_output_path": str(root / "final.ts"),
                    "segment_start_time": datetime.now()
                    - timedelta(minutes=150 + index),
                }
                await manager._finalize_segmented_recording(segments)
                assert admitted == [(8, segments["final_output_path"])]
                await run_in_thread_pool(
                    subprocess.run,
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-xerror",
                        "-i",
                        segments["final_output_path"],
                        "-f",
                        "null",
                        "-",
                    ],
                    check=True,
                    capture_output=True,
                )
        assert [owner for owner, _ in received] == [0, 1]
        if entry == "failure":
            assert all(
                "Streamlink exited with code 2" in message["message"]
                for _, message in received
            )
            for app in apps:
                events = await app.state.websocket_manager.get_events_since()
                assert len(events) == 1 and events[0]["type"] == "recording_failed"
                assert events[0]["data"]["stream_id"] == 7
                assert events[0]["data"]["streamer_id"] == 1
                assert events[0]["data"]["stream_title"] == f"Owner {apps.index(app)}"
        else:
            assert (
                "2h 30m" in received[0][1]["message"]
                and "720p" in received[0][1]["message"]
            )
            assert (
                "2h 31m" in received[1][1]["message"]
                and "480p" in received[1][1]["message"]
            )
        assert observed and get_ident() not in observed
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)
            if app.state.logging_service is not None:
                await run_in_thread_pool(app.state.logging_service.close)
        await runner.cleanup()
