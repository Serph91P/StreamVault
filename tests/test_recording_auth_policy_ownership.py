"""Recording admission reads dormant-priority/auth safety policy from its owner."""

import asyncio
import importlib
from threading import Event, get_ident
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import Stream, StreamerRecordingSettings
from app.services.recording.exceptions import ProcessError
from app.services.system.twitch_token_service import RecordingTokenResolution
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("codecs", [None, "hevc", "h264,hevc"])
async def test_recording_admission_uses_closed_owner_auth_policy(
    proxy_applications, monkeypatch, tmp_path, codecs
):
    applications, databases, _, queries = proxy_applications
    database_module = importlib.import_module("app.database")
    # A valid but foreign catalogue must never become this app's policy source.
    monkeypatch.setattr(
        database_module, "SessionLocal", databases[1].sync_session_factory
    )
    actors = []
    observed = []

    class AdmissionReached(Exception):
        pass

    try:
        for index, (app, database) in enumerate(
            zip(applications, databases, strict=True)
        ):
            with database.sync_session_factory() as session:
                session.add(Stream(id=1, streamer_id=1))
                session.add(
                    StreamerRecordingSettings(
                        streamer_id=1,
                        supported_codecs=codecs if index == 0 else "h264",
                        twitch_auth_priority=42,
                    )
                )
                session.commit()
        for index, app in enumerate(applications):
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            actor = await run_in_thread_pool(
                dependencies.get_application_recording_manager, connection
            )
            actors.append(actor)
            stream = await actor.orchestrator.database_service.get_stream_by_id(1)
            monkeypatch.setattr(
                actor.process_manager,
                "_resolve_recording_token",
                AsyncMock(
                    return_value=RecordingTokenResolution(
                        None, None, False, False, "fixture"
                    )
                ),
            )
            expected = index == 1 or not codecs or "h264" in codecs

            async def admission(**kwargs):
                observed.append(kwargs)
                assert kwargs["anonymous_available"] is expected
                assert kwargs["auth_priority"] == 0
                assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
                relevant = [
                    thread
                    for thread, sql in queries
                    if "streamer_recording_settings" in sql
                ]
                assert relevant and get_ident() not in relevant
                raise AdmissionReached

            monkeypatch.setattr(
                actor.process_manager.upstream_coordinator, "reserve", admission
            )
            queries.clear()
            with pytest.raises(ProcessError) as failure:
                await actor.process_manager.start_recording_process(
                    stream, str(tmp_path / "unused.ts"), "best"
                )
            assert isinstance(failure.value.__cause__, AdmissionReached)
        assert len(observed) == 2
        assert all(value["purpose"] == "RECORDING" for value in observed)
    finally:
        for actor in actors:
            await actor.process_manager.cleanup_all()
        for app in applications:
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()


@pytest.mark.asyncio
async def test_recording_auth_defaults_do_not_consume_foreign_configuration(
    proxy_applications, monkeypatch
):
    applications, databases, _, queries = proxy_applications
    connection = HTTPConnection({"type": "http", "app": applications[0], "headers": []})
    actor = await run_in_thread_pool(
        dependencies.get_application_recording_manager, connection
    )

    def forbidden():
        raise AssertionError("The default catalogue is not this application's owner")

    monkeypatch.setattr("app.database.SessionLocal", forbidden)
    try:
        queries.clear()
        assert await actor.process_manager._recording_auth_options(Stream(id=1)) == (
            0,
            True,
        )
        assert not queries
        # No per-channel row retains the existing anonymous-available default.
        assert await actor.process_manager._recording_auth_options(
            Stream(id=1, streamer_id=1)
        ) == (0, True)
        relevant = [
            thread for thread, sql in queries if "streamer_recording_settings" in sql
        ]
        assert relevant and get_ident() not in relevant
        assert databases[0].sync_engine.pool.checkedout() == 0
    finally:
        for app in applications:
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()


@pytest.mark.asyncio
async def test_recording_auth_cancellation_drains_its_actual_database_worker(
    proxy_applications,
):
    applications, databases, _, _ = proxy_applications
    connection = HTTPConnection({"type": "http", "app": applications[0], "headers": []})
    actor = await run_in_thread_pool(
        dependencies.get_application_recording_manager, connection
    )
    started, release, checked_in = Event(), Event(), Event()
    engine = databases[0].sync_engine

    def hold(connection, cursor, statement, parameters, context, executemany):
        if "streamer_recording_settings" in statement:
            started.set()
            assert release.wait(5)

    def check_in(connection, record):
        checked_in.set()

    event.listen(engine, "before_cursor_execute", hold)
    event.listen(engine, "checkin", check_in)
    task = asyncio.create_task(
        actor.process_manager._recording_auth_options(Stream(id=1, streamer_id=1))
    )
    try:
        assert await asyncio.to_thread(started.wait, 3)
        assert engine.pool.checkedout() == 1
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert checked_in.is_set()
        assert engine.pool.checkedout() == 0
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(checked_in.wait, 3)
        event.remove(engine, "before_cursor_execute", hold)
        event.remove(engine, "checkin", check_in)
        for app in applications:
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()
