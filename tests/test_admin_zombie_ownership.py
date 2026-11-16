"""Mounted zombie repair must use its real request-owned capture authority."""

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize("known_dead", [True, False])
async def test_admin_zombie_repair_stops_only_positively_dead_owned_catalogue(
    image_applications, monkeypatch, known_dead
):
    apps, databases, clients, queries = image_applications
    now = datetime.now(timezone.utc)
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )

    def seed():
        for database in databases:
            with database.sync_session_factory() as db:
                db.add(
                    Stream(id=70, streamer_id=1, started_at=now - timedelta(hours=2))
                )
                db.flush()
                db.add(
                    Recording(
                        id=7,
                        stream_id=70,
                        status="recording",
                        start_time=now - timedelta(hours=2),
                    )
                )
                db.commit()

    await run_in_thread_pool(seed)
    managers = [
        await run_in_thread_pool(
            dependencies.get_application_recording_manager,
            HTTPConnection({"type": "http", "app": app}),
        )
        for app in apps
    ]
    # Real exited child snapshots supply positive DEAD evidence, not an invented
    # cleanup result or inference from mere absence of a process.
    children = []
    owned_queries, listeners = [], []
    for index, database in enumerate(databases):

        def listener(*_args, index=index):
            owned_queries.append((index, get_ident()))

        event.listen(database.sync_engine, "before_cursor_execute", listener)
        listeners.append(listener)
    try:
        for index, manager in enumerate(managers):
            if index == 0 and not known_dead:
                continue
            child = await asyncio.create_subprocess_exec("python", "-c", "pass")
            await child.wait()
            children.append(child)
            manager.process_manager.active_processes["stream_70"] = child
        startup = importlib.import_module("app.services.init.startup_init")
        monkeypatch.setattr(startup, "get_recording_manager", lambda: managers[1])
        queries.clear()
        response = await clients[0].post("/api/admin/recordings/cleanup-zombies")
        assert response.status_code == 200, response.text
        assert response.json()["cleaned_count"] == (1 if known_dead else 0)
        assert owned_queries and {owner for owner, _thread in owned_queries} == {0}
        assert get_ident() not in {thread for _owner, thread in owned_queries}
        for index, database in enumerate(databases):
            with database.sync_session_factory() as db:
                recording = db.get(Recording, 7)
                assert recording.status == (
                    "stopped" if index == 0 and known_dead else "recording"
                )
                assert (recording.end_time is not None) is (index == 0 and known_dead)
    finally:
        for database, listener in zip(databases, listeners, strict=True):
            event.remove(database.sync_engine, "before_cursor_execute", listener)
        for child in children:
            await child.wait()
        await close_owned(apps)
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)
