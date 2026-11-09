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
