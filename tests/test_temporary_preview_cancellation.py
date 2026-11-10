"""Preview cancellation must drain the actual owner transaction before returning."""

import asyncio
from contextlib import contextmanager
from threading import Event

import pytest
from sqlalchemy import text

from app.database import Base, DatabaseLifecycle
from app.services.system import temporary_cleanup_service as cleanup
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_preview_repeated_cancellation_waits_for_its_owned_session(
    tmp_path, monkeypatch
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'preview.db'}")
    with database.sync_engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    entered, release, closed = Event(), Event(), Event()
    original = cleanup._inspect

    @contextmanager
    def sessions():
        try:
            with database.sync_session_factory() as session:
                yield session
        finally:
            closed.set()

    def held(session, *args, **kwargs):
        session.execute(text("SELECT 1"))
        entered.set()
        assert release.wait(10), "fixture must release its held preview"
        return original(session, *args, **kwargs)

    monkeypatch.setattr(cleanup, "_inspect", held)
    task = asyncio.create_task(
        cleanup.cleanup_temporary_files(
            tmp_path, sessions, cleanup.TemporaryCleanupRequest()
        )
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "caller returned before its worker/session drained"
        assert not closed.is_set()
        assert database.sync_engine.pool.checkedout() == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set()
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(closed.wait, 10)
        await run_in_thread_pool(database.sync_engine.dispose)
