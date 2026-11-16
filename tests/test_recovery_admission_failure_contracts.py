"""Native discovery/admission races and storage failures, no decoder/provider claim."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import BackgroundTask, Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.retry_decorator import NonRetryableError
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    ["valid", "missing-file", "missing-row", "unwritable", "rejected-admission"],
)
async def test_native_retry_revalidates_discovered_values_before_acknowledging_admission(
    image_applications, monkeypatch, change
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    for owner in apps:
        monkeypatch.setattr(
            owner.state.settings,
            "LOGS_BASE_DIR",
            owner.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    path = Path(app.state.settings.RECORDING_DIRECTORY) / "failed.ts"
    with path.open("wb") as source:
        source.truncate(2 * 1024 * 1024)
    now = datetime.now(timezone.utc)

    def seed():
        with database.sync_session_factory() as db:
            db.add(
                Stream(
                    id=70,
                    streamer_id=1,
                    title="Owned retry",
                    started_at=now - timedelta(hours=2),
                    ended_at=now - timedelta(hours=1),
                )
            )
            db.flush()
            db.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="stopped",
                    path=str(path),
                    start_time=now - timedelta(hours=2),
                )
            )
            db.commit()

    await run_in_thread_pool(seed)
    service = await run_in_thread_pool(
        dependencies.get_application_recovery_service,
        HTTPConnection({"type": "http", "app": app}),
    )
    native_scan = service._scan_failed_post_processing

    async def scan(max_age_hours):
        values = await native_scan(max_age_hours)
        assert len(values) == 1 and values[0]["recording_id"] == 7

        def mutate():
            if change == "missing-file":
                path.unlink()
            elif change == "missing-row":
                with database.sync_session_factory() as db:
                    db.delete(db.get(Recording, 7))
                    db.commit()

        await run_in_thread_pool(mutate)
        return values  # Native unchanged DTOs, not invented discovery results.

    monkeypatch.setattr(service, "_scan_failed_post_processing", scan)
    native_temporary = tempfile.TemporaryFile
    faults = []

    def temporary(*args, **kwargs):
        if (
            change == "unwritable"
            and kwargs.get("dir") is not None
            and Path(kwargs["dir"]) == path.parent
        ):
            faults.append((change, threading.get_ident()))
            raise PermissionError("synthetic-owned-output-unwritable")
        return native_temporary(*args, **kwargs)

    monkeypatch.setattr(tempfile, "TemporaryFile", temporary)
    loop_thread = threading.get_ident()
    queries = []

    def sql(_connection, _cursor, statement, *_args):
        queries.append(threading.get_ident())
        if change == "rejected-admission" and statement.lstrip().upper().startswith(
            "INSERT INTO BACKGROUND_TASKS"
        ):
            faults.append((change, threading.get_ident()))
            raise NonRetryableError("synthetic-owned-admission-rejected")

    event.listen(database.sync_engine, "before_cursor_execute", sql)
    try:
        admitted = await service.retry_failed_recordings()
        assert admitted == (1 if change == "valid" else 0)
        assert queries and loop_thread not in queries
        if change in {"unwritable", "rejected-admission"}:
            assert [kind for kind, _thread in faults] == [change]
            assert all(thread != loop_thread for _kind, thread in faults)
        event.remove(database.sync_engine, "before_cursor_execute", sql)
        with database.sync_session_factory() as db:
            assert (db.query(BackgroundTask).count() > 0) is (change == "valid")
            if change != "missing-row":
                assert db.get(Recording, 7).status == "stopped"
        with databases[1].sync_session_factory() as db:
            assert db.query(BackgroundTask).count() == 0
        assert path.exists() is (change != "missing-file")
        if path.exists():
            assert path.stat().st_size == 2 * 1024 * 1024
    finally:
        if event.contains(database.sync_engine, "before_cursor_execute", sql):
            event.remove(database.sync_engine, "before_cursor_execute", sql)
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
