"""Offline EventSub commits closed catalog snapshots before notifying/stopping."""

import asyncio
import json
from datetime import datetime, timezone
from threading import get_ident, Event
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.services.communication.websocket_manager import ConnectionManager
from app.events import handler_registry as module
from app.models import Recording, Stream, Streamer
from tests.test_external_notification_boundary import notification_catalogs as _catalogs

notification_catalogs = _catalogs


@pytest.mark.asyncio
@pytest.mark.parametrize("open_streams", [True, False])
async def test_offline_event_uses_own_closed_workers_before_notifications_and_stop(
    notification_catalogs, monkeypatch, open_streams
):
    databases = notification_catalogs
    notifications, stopped, queries = [], [], []
    loop_thread = get_ident()
    registries = []
    started = datetime(2026, 7, 9, 12, tzinfo=timezone.utc)
    for index, database in enumerate(databases):
        with database.sync_session_factory() as session:
            session.get(Streamer, 1).is_live = True
            for stream_id, day in ((10, 8), (20, 9)):
                session.add(
                    Stream(
                        id=stream_id,
                        streamer_id=1,
                        twitch_stream_id=f"{index}-{stream_id}",
                        title=f"title-{stream_id}",
                        category_name="Games",
                        started_at=started.replace(day=day),
                        created_at=started.replace(day=day),
                        ended_at=None if open_streams else started,
                    )
                )
                session.flush()
                session.add(
                    Recording(
                        id=stream_id,
                        stream_id=stream_id,
                        status="recording",
                        start_time=started,
                    )
                )
            session.commit()
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *args: queries.append(get_ident()),
        )

        class Notifications:
            def __init__(self, owner, database):
                self.owner, self.database = owner, database

            async def send_stream_notification(
                self, *, streamer_name, event_type, details
            ):
                assert self.database.sync_engine.pool.checkedout() == 0
                assert get_ident() == loop_thread
                notifications.append(
                    (
                        self.owner,
                        streamer_name,
                        event_type,
                        json.loads(json.dumps(details)),
                    )
                )

        class Recorder:
            def __init__(self, owner, database):
                self.owner, self.database = owner, database

            async def stop_recording(self, recording_id, *, reason):
                assert self.database.sync_engine.pool.checkedout() == 0
                assert get_ident() == loop_thread
                assert (
                    len([item for item in notifications if item[0] == self.owner]) == 1
                )
                stopped.append((self.owner, recording_id, reason))

        registries.append(
            module.EventHandlerRegistry(
                ConnectionManager(),
                settings=Settings(ENVIRONMENT="test", _env_file=None),
                session_factory=database.sync_session_factory,
                recording_manager=Recorder(index, database),
                notification_service=Notifications(index, database),
            )
        )

    def forbidden_default():
        raise AssertionError("Offline event must not open the default catalog")

    monkeypatch.setattr(module, "SessionLocal", forbidden_default)
    try:
        await asyncio.gather(
            *(
                registry.handle_stream_offline(
                    {
                        "broadcaster_user_id": name,
                        "broadcaster_user_name": "channel",
                        "broadcaster_user_login": "channel",
                    }
                )
                for registry, name in zip(registries, ("first", "second"))
            )
        )
        assert sorted(stopped) == [(0, 20, "automatic"), (1, 20, "automatic")]
        assert len(notifications) == 2
        for owner, username, kind, details in notifications:
            assert username == "channel" and kind == "offline"
            assert details == {
                "streamer_id": 1,
                "stream_id": 20 if open_streams else None,
                "url": "https://twitch.tv/channel",
                "profile_image_url": "/recordings/.media/profiles/profile_avatar_1.jpg",
                "twitch_login": "channel",
                "is_live": False,
            }
        assert queries and loop_thread not in queries
        for database in databases:
            with database.sync_session_factory() as session:
                assert session.get(Streamer, 1).is_live is False
                assert all(
                    row.ended_at is not None for row in session.query(Stream).all()
                )
                # This test observes the stop command, not a physical capture stop.
                assert session.get(Recording, 10).status == "recording"
                if open_streams:
                    assert session.get(Streamer, 1).last_stream_title == "title-20"
        before = len(stopped), len(notifications)
        await registries[0].handle_stream_offline(
            {"broadcaster_user_id": "unknown", "broadcaster_user_login": "unknown"}
        )
        assert (len(stopped), len(notifications)) == before
    finally:
        for registry in registries:
            await registry.manager.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_streams", [True, False])
async def test_offline_without_active_capture_keeps_catalog_notification(
    notification_catalogs, empty_streams
):
    database = notification_catalogs[0]
    now = datetime.now(timezone.utc)
    if not empty_streams:
        with database.sync_session_factory() as session:
            session.add(Stream(id=20, streamer_id=1, started_at=now, ended_at=now))
            session.flush()
            session.add(
                Recording(id=20, stream_id=20, status="completed", start_time=now)
            )
            session.commit()
    notifications, stops = [], []

    async def notify(**kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        notifications.append(kwargs)

    async def stop(*args, **kwargs):
        stops.append(args)

    registry = module.EventHandlerRegistry(
        ConnectionManager(),
        session_factory=database.sync_session_factory,
        recording_manager=SimpleNamespace(stop_recording=stop),
        notification_service=SimpleNamespace(send_stream_notification=notify),
    )
    try:
        await registry.handle_stream_offline(
            {"broadcaster_user_id": "first", "broadcaster_user_login": "channel"}
        )
        assert stops == [] and len(notifications) == 1
        assert notifications[0]["details"]["stream_id"] is None
        with database.sync_session_factory() as session:
            assert session.get(Streamer, 1).is_live is False
            if not empty_streams:
                assert session.get(Recording, 20).status == "completed"
    finally:
        await registry.manager.close_all()


@pytest.mark.asyncio
async def test_offline_worker_failure_rolls_back_without_notify_or_stop(
    notification_catalogs,
):
    from sqlalchemy.exc import SQLAlchemyError

    database = notification_catalogs[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).is_live = True
        session.add(Stream(id=20, streamer_id=1, started_at=datetime.now(timezone.utc)))
        session.commit()
    effects = []

    async def unexpected(*args, **kwargs):
        effects.append((args, kwargs))

    def fail_stream_update(connection, cursor, statement, *args):
        if statement.lower().startswith("update streams "):
            raise SQLAlchemyError("injected update failure")

    event.listen(database.sync_engine, "before_cursor_execute", fail_stream_update)
    registry = module.EventHandlerRegistry(
        ConnectionManager(),
        session_factory=database.sync_session_factory,
        recording_manager=SimpleNamespace(stop_recording=unexpected),
        notification_service=SimpleNamespace(send_stream_notification=unexpected),
    )
    try:
        await registry.handle_stream_offline(
            {"broadcaster_user_id": "first", "broadcaster_user_login": "channel"}
        )
        assert effects == []
        assert database.sync_engine.pool.checkedout() == 0
        with database.sync_session_factory() as session:
            assert session.get(Streamer, 1).is_live is True
            assert session.get(Stream, 20).ended_at is None
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", fail_stream_update)
        await registry.manager.close_all()


@pytest.mark.asyncio
async def test_cancelled_offline_drains_its_actual_catalog_worker(
    notification_catalogs, monkeypatch
):
    database = notification_catalogs[0]
    entered, release, worker_done = Event(), Event(), Event()
    effects = []
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).is_live = True
        session.commit()
    original = module.prepare_offline

    def tracked_prepare(*args):
        try:
            return original(*args)
        finally:
            worker_done.set()

    monkeypatch.setattr(module, "prepare_offline", tracked_prepare)

    def hold_update(connection, cursor, statement, *args):
        if statement.lower().startswith("update streamers "):
            entered.set()
            assert release.wait(10)

    event.listen(database.sync_engine, "before_cursor_execute", hold_update)

    async def unexpected(*args, **kwargs):
        effects.append((args, kwargs))

    registry = module.EventHandlerRegistry(
        ConnectionManager(),
        session_factory=database.sync_session_factory,
        recording_manager=SimpleNamespace(stop_recording=unexpected),
        notification_service=SimpleNamespace(send_stream_notification=unexpected),
    )
    task = asyncio.create_task(
        registry.handle_stream_offline(
            {"broadcaster_user_id": "first", "broadcaster_user_login": "channel"}
        )
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        assert database.sync_engine.pool.checkedout() == 1
        for _ in range(2):
            task.cancel()
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), 0.05)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert worker_done.is_set()
        assert database.sync_engine.pool.checkedout() == 0
        assert effects == []
        with database.sync_session_factory() as session:
            assert session.get(Streamer, 1).is_live is False
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(worker_done.wait, 5)
        event.remove(database.sync_engine, "before_cursor_execute", hold_update)
        await registry.manager.close_all()


@pytest.mark.asyncio
async def test_offline_recording_lookup_remains_fresh_after_notification(
    notification_catalogs,
):
    database = notification_catalogs[0]
    now = datetime.now(timezone.utc)
    with database.sync_session_factory() as session:
        session.add(Stream(id=20, streamer_id=1, started_at=now))
        session.flush()
        session.add(Recording(id=20, stream_id=20, status="recording", start_time=now))
        session.commit()
    stopped = []

    async def notify(**kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        with database.sync_session_factory() as session:
            session.get(Recording, 20).status = "completed"
            session.add(
                Recording(id=21, stream_id=20, status="recording", start_time=now)
            )
            session.commit()

    async def stop(recording_id, **kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        stopped.append(recording_id)

    registry = module.EventHandlerRegistry(
        ConnectionManager(),
        session_factory=database.sync_session_factory,
        recording_manager=SimpleNamespace(stop_recording=stop),
        notification_service=SimpleNamespace(send_stream_notification=notify),
    )
    try:
        await registry.handle_stream_offline(
            {"broadcaster_user_id": "first", "broadcaster_user_login": "channel"}
        )
        assert stopped == [21]
        with database.sync_session_factory() as session:
            assert session.get(Stream, 20).ended_at is not None
            assert session.get(Recording, 20).status == "completed"
    finally:
        await registry.manager.close_all()
