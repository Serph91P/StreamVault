"""Admin repair preserves actual file ownership and runs scoped SQL/file work natively."""

from pathlib import Path
from datetime import datetime, timezone
from threading import get_ident

import pytest

from app import database as database_module
from app.models import Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications
from test_video_catalog_timestamps import catalog_sessions


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_admin_availability_repair_is_native_and_catalogue_owned(
    image_applications, monkeypatch, dry_run
):
    apps, databases, clients, queries = image_applications
    files = [Path(app.state.settings.RECORDING_DIRECTORY) / "owned.ts" for app in apps]
    observed = []
    defaults = []
    native_stat = Path.stat

    def forbidden():
        defaults.append(True)
        raise AssertionError("admin repair borrowed default catalogue")

    def stat(path, *args, **kwargs):
        if path in files:
            observed.append(get_ident())
        return native_stat(path, *args, **kwargs)

    def seed(index):
        files[index].write_bytes(f"owner-{index}".encode())
        with databases[index].sync_session_factory() as db:
            db.add(Stream(id=71, streamer_id=1, title=f"owner-{index}"))
            db.flush()
            db.add(
                Recording(
                    id=72,
                    stream_id=71,
                    status="completed",
                    start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    path=str(files[index]),
                )
            )
            db.commit()

    for index in range(2):
        await run_in_thread_pool(seed, index)
    monkeypatch.setattr(database_module, "SessionLocal", forbidden)
    monkeypatch.setattr(Path, "stat", stat)
    queries.clear()
    response = await clients[0].post(
        "/api/admin/recordings/fix-availability",
        params={"dry_run": str(dry_run).lower()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["fixed"] == 1
    assert queries and get_ident() not in [thread for thread, _ in queries]
    assert observed and get_ident() not in observed
    assert not defaults

    def snapshot(index):
        with databases[index].sync_session_factory() as db:
            return db.get(Stream, 71).recording_path

    assert await run_in_thread_pool(snapshot, 0) == (None if dry_run else str(files[0]))
    assert await run_in_thread_pool(snapshot, 1) is None
    assert [file.read_bytes() for file in files] == [b"owner-0", b"owner-1"]
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
async def test_admin_availability_database_fault_is_local_and_closes_session(
    image_applications,
):
    from sqlalchemy import event

    _, databases, clients, _ = image_applications

    def fail_stream_query(_, __, statement, *___):
        if "FROM streams" in statement:
            raise RuntimeError("synthetic catalogue outage")

    event.listen(databases[0].sync_engine, "before_cursor_execute", fail_stream_query)
    try:
        response = await clients[0].post("/api/admin/recordings/fix-availability")
        assert response.status_code == 500
        assert response.json() == {"detail": "Recording fix failed"}
        healthy = await clients[1].post("/api/admin/recordings/fix-availability")
        assert healthy.status_code == 200
        assert healthy.json()["data"]["checked"] == 0
    finally:
        event.remove(
            databases[0].sync_engine, "before_cursor_execute", fail_stream_query
        )
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["cleanup-orphaned-db", "cleanup-process-orphaned"]
)
async def test_admin_cleanup_preview_is_owned_native_and_keeps_unproven_capture(
    image_applications, monkeypatch, operation
):
    _, databases, clients, queries = image_applications
    defaults = []

    def forbidden():
        defaults.append(True)
        raise AssertionError("cleanup preview borrowed default catalogue")

    def seed(index):
        with databases[index].sync_session_factory() as db:
            db.add(Stream(id=71, streamer_id=1, title=f"owner-{index}"))
            db.flush()
            db.add(
                Recording(
                    id=72,
                    stream_id=71,
                    status="recording",
                    start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                )
            )
            db.commit()

    for index in range(2):
        await run_in_thread_pool(seed, index)
    monkeypatch.setattr(database_module, "SessionLocal", forbidden)
    queries.clear()
    response = await clients[0].post(
        f"/api/admin/recordings/{operation}", params={"dry_run": "true"}
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["checked"] == 1 and result["errors"] == 0
    assert result["cleaned"] == 0 and result["details"][0]["action"] == "none"
    assert not defaults
    assert queries and get_ident() not in [thread for thread, _ in queries]

    def status(index):
        with databases[index].sync_session_factory() as db:
            return db.get(Recording, 72).status

    assert await run_in_thread_pool(status, 0) == "recording"
    assert await run_in_thread_pool(status, 1) == "recording"
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["cleanup-orphaned-db", "cleanup-process-orphaned"]
)
@pytest.mark.parametrize("state", ["alive", "dead", "unknown", "absent"])
@pytest.mark.parametrize("dry_run", [True, False])
async def test_admin_cleanup_requires_real_death_and_never_changes_peer(
    image_applications, operation, state, dry_run
):
    import subprocess
    import sys
    from datetime import timedelta

    from app.models import Streamer, TwitchUpstreamLease
    from app.services.twitch_upstream_coordinator import ProcessInspector

    apps, databases, clients, queries = image_applications
    child = None
    identity = None
    files = [
        Path(app.state.settings.RECORDING_DIRECTORY) / "capture.ts" for app in apps
    ]
    try:
        if state in {"alive", "dead"}:
            child = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                start_new_session=True,
            )
            identity = await run_in_thread_pool(ProcessInspector().inspect, child.pid)
            if state == "dead":
                child.terminate()
                await run_in_thread_pool(child.wait, timeout=3)

        def seed(index):
            files[index].write_bytes(f"capture-{index}".encode())
            with databases[index].sync_session_factory() as db:
                db.add(Stream(id=71, streamer_id=1, title=f"owner-{index}"))
                db.flush()
                started = datetime(2026, 1, 1, tzinfo=timezone.utc)
                db.add(
                    Recording(
                        id=72,
                        stream_id=71,
                        status="recording",
                        path=str(files[index]),
                        start_time=started,
                    )
                )
                db.flush()
                if state != "absent":
                    db.add(
                        TwitchUpstreamLease(
                            channel_key=db.get(Streamer, 1).twitch_id,
                            recording_id=72,
                            purpose="RECORDING",
                            state="STARTING" if state == "unknown" else "ACTIVE",
                            generation=1,
                            process_pid=child.pid if child else None,
                            process_group_id=identity.process_group_id
                            if identity
                            else None,
                            process_started_at=identity.started_at
                            if identity
                            else None,
                            process_start_fingerprint=identity.fingerprint
                            if identity
                            else None,
                            reserved_at=started,
                            heartbeat_at=started,
                            expires_at=started + timedelta(minutes=5),
                            created_at=started,
                            updated_at=started,
                        )
                    )
                db.commit()

        for index in range(2):
            await run_in_thread_pool(seed, index)
        queries.clear()
        response = await clients[0].post(
            f"/api/admin/recordings/{operation}",
            params={"dry_run": str(dry_run).lower()},
        )
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["checked"] == 1 and result["errors"] == 0
        assert result["details"][0]["action"].startswith("mark_completed") is (
            state == "dead"
        )
        assert queries and get_ident() not in [thread for thread, _ in queries]

        def status(index):
            with databases[index].sync_session_factory() as db:
                return db.get(Recording, 72).status

        assert await run_in_thread_pool(status, 0) == (
            "completed" if state == "dead" and not dry_run else "recording"
        )
        assert await run_in_thread_pool(status, 1) == "recording"
        assert [file.read_bytes() for file in files] == [b"capture-0", b"capture-1"]
        if state == "alive":
            assert child.poll() is None
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
            await run_in_thread_pool(child.wait, timeout=3)


@pytest.mark.parametrize("catalog_sessions", ["postgres"], indirect=True)
@pytest.mark.parametrize("max_age_hours", [None, 48])
@pytest.mark.parametrize("alive", [True, False])
def test_postgres_admin_cleanup_guarded_rows_preserve_live_capture(
    catalog_sessions, max_age_hours, alive
):
    import asyncio
    import subprocess
    import sys
    from time import monotonic

    from app.database import Base
    from app.models import Streamer
    from app.services.recording.admin_cleanup import _inspect_recordings
    from app.services.recording.media_ownership import LocalCapture
    from app.services.twitch_upstream_coordinator import (
        ProcessInspector,
        TwitchUpstreamCoordinator,
    )

    factory, _ = catalog_sessions
    Base.metadata.create_all(factory.kw["bind"])
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        identity = ProcessInspector().inspect(child.pid)
        if not alive:
            child.terminate()
            child.wait(timeout=3)
        with factory() as db:
            channel = Streamer(username="cleanup-pg", twitch_id="cleanup-pg")
            db.add(channel)
            db.flush()
            stream = Stream(streamer_id=channel.id, title="cleanup-pg")
            db.add(stream)
            db.flush()
            row = Recording(
                stream_id=stream.id,
                status="recording",
                start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            db.add(row)
            db.commit()
            recording_id, stream_id = row.id, stream.id
        snapshots = {
            f"stream_{stream_id}": LocalCapture(
                child.pid, identity.process_group_id, identity.fingerprint, False
            )
        }
        result = asyncio.run(
            TwitchUpstreamCoordinator(
                factory, monotonic_clock=monotonic
            ).run_capture_maintenance(
                lambda db: _inspect_recordings(
                    db, snapshots, dry_run=False, max_age_hours=max_age_hours
                )
            )
        )
        assert result["checked"] == 1 and result["errors"] == 0
        assert result["cleaned"] == int(not alive)
        with factory() as db:
            assert db.get(Recording, recording_id).status == (
                "recording" if alive else "completed"
            )
        if alive:
            assert child.poll() is None
        assert factory.kw["bind"].pool.checkedout() == 0
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=3)
