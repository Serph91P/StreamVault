"""Native recovery orchestration through owned HTTP/DAO/recording child ports.

Synthetic HTTP and a controlled actual OS child stand in for provider capture;
this proves delegation/persistence, not upstream reserve/activation/fencing.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from aiohttp import web
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import BackgroundTask, Recording, Stream, TwitchUpstreamLease
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["resumed", "failed", "bookkeeping-denied"])
async def test_live_orphan_recovery_resumes_owned_recording_without_premature_media_admission(
    image_applications, monkeypatch, outcome
):
    resumed = outcome != "failed"
    apps, databases, _clients, queries = image_applications
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    app, database = apps[0], databases[0]
    app.state.settings.TWITCH_APP_ID = "owned-resume-control"
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app}),
    )
    service = await run_in_thread_pool(
        dependencies.get_application_recovery_service,
        HTTPConnection({"type": "http", "app": app}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    root = Path(app.state.settings.RECORDING_DIRECTORY)
    segments = root / "capture_segments"
    segments.mkdir()
    segment = segments / "001.ts"
    segment.write_bytes(b"existing segments must not be prematurely concatenated")
    output = root / "capture.ts"
    now = datetime.now(timezone.utc)
    old = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time;print('ready',flush=True);time.sleep(60)",
        stdout=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    assert await old.stdout.readline() == b"ready\n"
    identity = (
        await manager.process_manager.upstream_coordinator.inspect_process_identity(
            old.pid
        )
    )
    old.kill()
    await old.wait()

    def seed():
        with database.sync_session_factory() as db:
            db.add(Stream(id=70, streamer_id=1, started_at=now - timedelta(hours=1)))
            db.flush()
            db.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="recording",
                    path=str(output),
                    start_time=now - timedelta(hours=1),
                )
            )
            db.flush()
            db.add(
                TwitchUpstreamLease(
                    channel_key="owner-0",
                    recording_id=7,
                    purpose="RECORDING",
                    state="ACTIVE",
                    generation=1,
                    process_pid=old.pid,
                    process_group_id=identity.process_group_id,
                    process_started_at=identity.started_at,
                    process_start_fingerprint=identity.fingerprint,
                    reserved_at=now,
                    heartbeat_at=now,
                    created_at=now,
                    updated_at=now,
                    expires_at=now + timedelta(minutes=1),
                )
            )
            db.commit()

    await run_in_thread_pool(seed)
    seen, children, starts = [], [], []

    async def streams(request):
        seen.append((request.headers["Client-ID"], request.query["user_id"]))
        assert database.sync_engine.pool.checkedout() == 0
        return web.json_response({"data": [{"id": "controlled-live"}]})

    provider = web.Application()
    provider.router.add_get("/helix/streams", streams)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    api = lifecycle._twitch_api_service
    api.base_url = f"http://127.0.0.1:{runner.addresses[0][1]}/helix"
    api._access_token = "synthetic-resume-control"
    api._token_expires_at = float("inf")

    async def spawn(**kwargs):
        starts.append(kwargs)
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import sys,time;from pathlib import Path;Path(sys.argv[1]).write_bytes(b'controlled resumed child');print('ready',flush=True);time.sleep(60)",
            kwargs["output_path"],
            stdout=asyncio.subprocess.PIPE,
        )
        children.append(child)
        assert await child.stdout.readline() == b"ready\n"
        if not resumed:
            child.terminate()
            await child.wait()
            raise RuntimeError("synthetic-owned-child-start-failed")
        return child

    async def monitor(_identity):
        await asyncio.Event().wait()

    monkeypatch.setattr(manager.process_manager, "start_recording_process", spawn)
    monkeypatch.setattr(lifecycle, "monitor_and_process_recording", monitor)
    faults = []

    def deny_prior_update(_connection, _cursor, statement, parameters, *_args):
        if (
            outcome == "bookkeeping-denied"
            and statement.lstrip().upper().startswith("UPDATE RECORDINGS ")
            and parameters[-1] == 7
        ):
            from threading import get_ident

            faults.append(get_ident())
            raise RuntimeError("synthetic-prior-recording-bookkeeping-denied")

    event.listen(database.sync_engine, "before_cursor_execute", deny_prior_update)
    try:
        queries.clear()
        accepted = await service._process_orphaned_recording(
            {
                "recording_id": 7,
                "segments_dir": segments,
                "expected_ts_path": output,
                "streamer_name": "owner-0",
            }
        )
        assert accepted is resumed
        assert seen == [("owned-resume-control", "owner-0")]
        assert len(starts) == 1 and starts[0]["recovery_generation"] == 1
        from threading import get_ident

        assert queries and get_ident() not in {thread for thread, _sql in queries}
        with database.sync_session_factory() as db:
            prior = db.get(Recording, 7)
            assert prior.status == ("stopped" if outcome == "resumed" else "recording")
            assert (prior.end_time is not None) is (outcome == "resumed")
            new_recording = db.query(Recording).filter(Recording.id != 7).one()
            assert new_recording.stream_id == 70
            assert new_recording.status == ("recording" if resumed else "failed")
            assert Path(new_recording.path).read_bytes() == b"controlled resumed child"
            assert db.query(BackgroundTask).count() == 0
        with databases[1].sync_session_factory() as db:
            assert db.query(Recording).count() == 0
        assert (
            segment.read_bytes()
            == b"existing segments must not be prematurely concatenated"
        )
        assert not output.exists()
        assert bool(faults) is (outcome == "bookkeeping-denied")
        assert get_ident() not in faults
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", deny_prior_update)
        for child in children:
            if child.returncode is None:
                child.terminate()
            await child.wait()
        await close_owned(apps)
        await runner.cleanup()
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
