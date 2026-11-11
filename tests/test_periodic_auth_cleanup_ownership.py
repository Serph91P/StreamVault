"""Periodic auth cleanup owns its database scope and stays off the event loop."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe
import threading

import pytest
from sqlalchemy import event

from app.config.settings import get_settings
from app.database import Base, DatabaseLifecycle
from app.models import Session, User
from app.lifespan import _run_session_cleanup


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entrypoint", ["lifespan-periodic", "startup-initial-and-periodic"]
)
async def test_periodic_session_cleanup_uses_only_its_factory_off_loop(
    tmp_path: Path, monkeypatch, entrypoint
) -> None:
    import app.lifespan as module

    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("cleanup-own", "cleanup-peer")
    ]
    settings = get_settings().model_copy(deep=True)
    loop_thread = threading.get_ident()
    query_threads = []
    now = datetime.now(timezone.utc)
    for database in databases:
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as db:
            db.add(User(id=1, username="cleanup-admin", password="***"))  # ggignore
            db.flush()
            db.add_all(
                [
                    Session(
                        user_id=1,
                        token=token_urlsafe(32),
                        created_at=now - timedelta(days=30),
                    ),
                    Session(user_id=1, token=token_urlsafe(32), created_at=now),
                ]
            )
            db.commit()

    def record_thread(*_args):
        query_threads.append(threading.get_ident())

    event.listen(databases[0].sync_engine, "before_cursor_execute", record_thread)
    sleeps = 0

    async def one_cycle(delay):
        nonlocal sleeps
        assert delay == 6 * 3600
        sleeps += 1
        if sleeps == 2:
            raise asyncio.CancelledError

    def foreign_session():
        raise AssertionError("periodic job borrowed the process-default session")

    monkeypatch.setattr(module, "SessionLocal", foreign_session)
    try:
        if entrypoint == "lifespan-periodic":
            monkeypatch.setattr(module.asyncio, "sleep", one_cycle)
            with pytest.raises(asyncio.CancelledError):
                await _run_session_cleanup(databases[0].sync_session_factory, settings)
        else:
            from app.services.init.startup_init import start_session_cleanup_service
            from app.services.system.supervisor import TaskSupervisor

            supervisor = TaskSupervisor("test-session-cleanup")
            try:
                await start_session_cleanup_service(
                    supervisor, databases[0].sync_session_factory, settings
                )
            finally:
                await supervisor.shutdown()
        assert query_threads and all(thread != loop_thread for thread in query_threads)
        event.remove(databases[0].sync_engine, "before_cursor_execute", record_thread)
        with databases[0].sync_session_factory() as db:
            assert db.query(Session).count() == 1
        with databases[1].sync_session_factory() as db:
            assert db.query(Session).count() == 2
    finally:
        for database in databases:
            await database.adispose()
