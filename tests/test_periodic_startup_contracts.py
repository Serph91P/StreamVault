"""Startup maintenance owns real DB scopes; timed work recovers and drains."""

import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from threading import get_ident
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import (
    _close_application_logging,
    _close_application_proxy,
    _close_application_twitch,
)
from app.models import (
    BackgroundTask,
    Recording,
    Session,
    Stream,
    Streamer,
    TwitchUpstreamLease,
)
from app.services.system.supervisor import TaskSupervisor
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications

startup = importlib.import_module("app.services.init.startup_init")


class Ticks:
    """Only the startup module's clock; no global asyncio/scheduler replacement."""

    def __init__(self):
        self.pending = asyncio.Queue()

    async def sleep(self, delay):
        if delay == 0:
            await asyncio.sleep(0)
            return
        future = asyncio.get_running_loop().create_future()
        self.pending.put_nowait((delay, future))
        await future

    async def paused(self):
        return await asyncio.wait_for(self.pending.get(), 3)


@pytest.mark.asyncio
async def test_periodic_session_cleanup_recovers_sql_failure_and_drains_owner(
    image_applications, monkeypatch, caplog
):
    apps, databases, _, queries = image_applications
    database = databases[0]
    supervisor = TaskSupervisor("owned-session-maintenance")
    ticks = Ticks()
    monkeypatch.setattr(
        startup,
        "asyncio",
        SimpleNamespace(sleep=ticks.sleep, CancelledError=asyncio.CancelledError),
    )
    now = datetime.now(timezone.utc)

    def seed(db, token):
        with db.sync_session_factory() as session:
            session.add(Session(token=token, created_at=now - timedelta(days=365)))
            session.commit()

    def tokens(db):
        with db.sync_session_factory() as session:
            return tuple(
                session.scalars(
                    select(Session.token).where(
                        Session.token.in_(
                            (
                                "initial-expired-fixture",
                                "later-expired-fixture",
                                "untouched-peer-fixture",
                            )
                        )
                    )
                ).all()
            )

    await run_in_thread_pool(seed, database, "initial-expired-fixture")
    await run_in_thread_pool(seed, databases[1], "untouched-peer-fixture")
    fault = [False]

    def fail_one_select(_conn, _cursor, sql, *_):
        if fault[0] and "FROM sessions" in sql:
            fault[0] = False
            raise RuntimeError("synthetic-periodic-session-fault")

    event.listen(database.sync_engine, "before_cursor_execute", fail_one_select)
    try:
        queries.clear()
        await startup.start_session_cleanup_service(
            supervisor, database.sync_session_factory, apps[0].state.settings
        )
        assert "periodic-session-cleanup" in supervisor.task_names
        assert await run_in_thread_pool(tokens, database) == ()
        first_delay, first = await ticks.paused()
        await run_in_thread_pool(seed, database, "later-expired-fixture")
        fault[0] = True
        first.set_result(None)
        next_delay, second = await ticks.paused()
        assert "Error in periodic session cleanup" in caplog.text
        assert await run_in_thread_pool(tokens, database) == ("later-expired-fixture",)
        assert database.sync_engine.pool.checkedout() == 0
        second.set_result(None)
        third_delay, _ = await ticks.paused()
        assert (
            first_delay
            == next_delay
            == third_delay
            == startup.ASYNC_DELAYS.SESSION_CLEANUP_INTERVAL
        )
        assert await run_in_thread_pool(tokens, database) == ()
        assert await run_in_thread_pool(tokens, databases[1]) == (
            "untouched-peer-fixture",
        )
        assert queries and get_ident() not in {thread for thread, _ in queries}
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", fail_one_select)
        await supervisor.shutdown()
    assert supervisor.closed and supervisor.task_names == ()
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_initial_session_cleanup_failure_does_not_publish_running_task(
    image_applications, caplog
):
    apps, databases, _, _ = image_applications
    database = databases[0]
    supervisor = TaskSupervisor("failed-session-maintenance")

    def fail_select(_conn, _cursor, sql, *_):
        if "FROM sessions" in sql:
            raise RuntimeError("synthetic-initial-session-fault")

    event.listen(database.sync_engine, "before_cursor_execute", fail_select)
    try:
        await startup.start_session_cleanup_service(
            supervisor, database.sync_session_factory, apps[0].state.settings
        )
        assert supervisor.task_names == ()
        assert "Session cleanup disabled" in caplog.text
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", fail_select)
        await supervisor.shutdown()


@pytest.mark.asyncio
async def test_periodic_zombie_cleanup_reaps_only_proven_dead_owner_and_recovers(
    image_applications, monkeypatch, caplog
):
    apps, databases, _, queries = image_applications
    database = databases[0]
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": apps[0]}),
    )
    supervisor = TaskSupervisor("owned-zombie-maintenance")
    ticks = Ticks()
    monkeypatch.setattr(
        startup,
        "asyncio",
        SimpleNamespace(sleep=ticks.sleep, CancelledError=asyncio.CancelledError),
    )
    child = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "pass", start_new_session=True
    )
    await child.wait()
    now = datetime.now(timezone.utc)

    def seed(db):
        with db.sync_session_factory() as session:
            session.add(
                Stream(id=70, streamer_id=1, started_at=now - timedelta(hours=2))
            )
            session.flush()
            session.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="recording",
                    start_time=now - timedelta(hours=1),
                )
            )
            session.flush()
            session.add(
                TwitchUpstreamLease(
                    channel_key="owner-0",
                    recording_id=7,
                    purpose="RECORDING",
                    state="ACTIVE",
                    process_pid=child.pid,
                    process_group_id=child.pid,
                    process_start_fingerprint="reaped-fixture",
                    generation=11,
                    reserved_at=now,
                    heartbeat_at=now,
                    created_at=now,
                    updated_at=now,
                    expires_at=now + timedelta(hours=1),
                )
            )
            session.commit()

    def status(db):
        with db.sync_session_factory() as session:
            row = session.get(Recording, 7)
            return None if row is None else (row.status, row.end_time, row.duration)

    fault = [False]

    def fail_one_select(_conn, _cursor, sql, *_):
        if fault[0] and "FROM recordings" in sql:
            fault[0] = False
            raise RuntimeError("synthetic-periodic-zombie-fault")

    event.listen(database.sync_engine, "before_cursor_execute", fail_one_select)
    try:
        queries.clear()
        await startup.start_zombie_recording_cleanup_service(
            supervisor, recording_manager=manager
        )
        delay, first = await ticks.paused()
        assert delay == 300 and "periodic-zombie-cleanup" in supervisor.task_names
        await run_in_thread_pool(seed, database)
        manager.orchestrator.state_manager.add_active_recording(7, {"stream_id": 70})
        fault[0] = True
        first.set_result(None)
        _, second = await ticks.paused()
        assert "Error in periodic zombie cleanup" in caplog.text
        assert (await run_in_thread_pool(status, database))[0] == "recording"
        assert database.sync_engine.pool.checkedout() == 0
        second.set_result(None)
        await ticks.paused()
        row = await run_in_thread_pool(status, database)
        assert row[0] == "stopped" and row[1] is not None and row[2] >= 3600
        assert manager.orchestrator.state_manager.get_active_recording(7) is None
        assert await run_in_thread_pool(status, databases[1]) is None
        assert queries and get_ident() not in {thread for thread, _ in queries}
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", fail_one_select)
        await supervisor.shutdown()
        await manager.shutdown()
        await _close_application_proxy(apps[0])
        await _close_application_twitch(apps[0])
        await _close_application_logging(apps[0])
    assert supervisor.task_names == () and supervisor.closed
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.asyncio
async def test_complete_scoped_background_startup_executes_durable_recovery_and_shutdown(
    image_applications, monkeypatch
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    supervisor = TaskSupervisor("complete-owned-background")
    ticks = Ticks()
    monkeypatch.setattr(
        startup,
        "asyncio",
        SimpleNamespace(sleep=ticks.sleep, CancelledError=asyncio.CancelledError),
    )
    queue_manager = app.state.background_queue_manager
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app}),
    )
    images = await run_in_thread_pool(
        dependencies._get_application_auto_image_sync_service, app
    )

    def prepare():
        with database.sync_session_factory() as session:
            session.get(Streamer, 1).profile_image_url = None
            session.commit()

    def jobs(db):
        with db.sync_session_factory() as session:
            return tuple(
                (row.task_type, row.status, row.completed_at)
                for row in session.scalars(select(BackgroundTask)).all()
            )

    await run_in_thread_pool(prepare)
    try:
        pending = asyncio.create_task(
            startup.verify_queue_readiness(queue_service=queue_manager.queue_service)
        )
        for _ in range(2):
            _, tick = await ticks.paused()
            tick.set_result(None)
        assert await asyncio.wait_for(pending, 3) is False
        with pytest.raises(ValueError, match="requires its capture checker"):
            await startup.initialize_background_queue_with_fixes(
                queue_manager=queue_manager
            )
        assert queue_manager.is_initialized is False
        await startup.initialize_background_services(
            supervisor,
            session_factory=database.sync_session_factory,
            settings=app.state.settings,
            queue_manager=queue_manager,
            capture_checker=manager.is_capture_running,
            recording_manager=manager,
            twitch_api=app.state.twitch_api,
            image_sync_service=images,
        )
        assert queue_manager.is_initialized and queue_manager.queue_service.is_running
        assert await startup.verify_queue_readiness(
            queue_service=queue_manager.queue_service
        )
        await startup.initialize_background_queue_with_fixes(
            queue_manager=queue_manager, capture_checker=manager.is_capture_running
        )
        assert set(supervisor.task_names) == {
            "periodic-session-cleanup",
            "periodic-zombie-cleanup",
        }
        async with asyncio.timeout(15):
            while True:
                own_jobs = await run_in_thread_pool(jobs, database)
                recovered = [row for row in own_jobs if row[0] == "unified_recovery"]
                if recovered and all(
                    row[1] == "completed" and row[2] is not None for row in recovered
                ):
                    break
                await asyncio.sleep(0.01)
        assert len(recovered) == 1
        assert await run_in_thread_pool(jobs, databases[1]) == ()
        assert not apps[1].state.background_queue_manager.is_initialized
    finally:
        await startup.shutdown_background_services(
            supervisor, queue_manager=queue_manager, image_sync_service=images
        )
        await manager.shutdown()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await _close_application_logging(app)
    assert supervisor.closed and supervisor.task_names == ()
    assert not queue_manager.queue_service.is_running
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.asyncio
async def test_zombie_startup_sql_failure_does_not_register_periodic_task(
    image_applications, caplog
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app}),
    )
    supervisor = TaskSupervisor("failed-zombie-maintenance")

    def fail_select(_conn, _cursor, sql, *_):
        if sql.lstrip().upper().startswith("SELECT"):
            raise RuntimeError("synthetic-initial-zombie-sql-fault")

    event.listen(database.sync_engine, "before_cursor_execute", fail_select)
    try:
        await startup.start_zombie_recording_cleanup_service(
            supervisor, recording_manager=manager
        )
        assert supervisor.task_names == ()
        assert "Zombie cleanup disabled" in caplog.text
        assert database.sync_engine.pool.checkedout() == 0
        await startup.recover_active_recordings(
            session_factory=database.sync_session_factory,
            recording_manager=manager,
            twitch_api=app.state.twitch_api,
        )
        assert "Startup recording recovery failed" in caplog.text
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", fail_select)
        await supervisor.shutdown()
        await manager.shutdown()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await _close_application_logging(app)


@pytest.mark.asyncio
async def test_unified_startup_recovery_stopped_or_failed_queue_has_no_durable_job(
    image_applications, caplog
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app}),
    )
    queue_manager = app.state.background_queue_manager
    queue = queue_manager.queue_service
    try:
        await startup.unified_recovery_scan(queue_service=queue)
        assert "Background queue not running" in caplog.text
        await startup.initialize_background_queue_with_fixes(
            queue_manager=queue_manager, capture_checker=manager.is_capture_running
        )

        def reject_insert(_conn, _cursor, sql, *_):
            if sql.lstrip().upper().startswith("INSERT INTO BACKGROUND_TASKS"):
                raise RuntimeError("synthetic-startup-admission-fault")

        event.listen(database.sync_engine, "before_cursor_execute", reject_insert)
        try:
            await startup.unified_recovery_scan(queue_service=queue)
        finally:
            event.remove(database.sync_engine, "before_cursor_execute", reject_insert)
        assert "synthetic-startup-admission-fault" in caplog.text
    finally:
        await queue_manager.shutdown()
        await manager.shutdown()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await _close_application_logging(app)

    def jobs(db):
        with db.sync_session_factory() as session:
            return list(session.scalars(select(BackgroundTask)).all())

    assert await run_in_thread_pool(jobs, database) == []
    assert await run_in_thread_pool(jobs, databases[1]) == []
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
