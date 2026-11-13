"""Public two-app regressions for PR1070's B1–B3 resource boundaries."""

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, get_ident

import pytest
from sqlalchemy import event

from app.models import GlobalSettings, RecordingSettings, Stream
from app.services.system.cleanup_service import CleanupService
from app.services.system.persistent_key_service import PersistentKeyBootstrapService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
async def test_push_routes_use_bootstrapped_owner_identity(image_applications):
    apps, databases, clients, _ = image_applications
    for app, db in zip(apps, databases):
        await run_in_thread_pool(
            PersistentKeyBootstrapService(db.sync_session_factory).bootstrap,
            app.state.settings,
        )
    assert (
        apps[0].state.settings.VAPID_PUBLIC_KEY
        != apps[1].state.settings.VAPID_PUBLIC_KEY
    )
    for app, client in zip(apps, clients):
        response = await client.get("/api/push/vapid-public-key")
        assert response.status_code == 200
        assert response.json() == {
            "publicKey": app.state.settings.VAPID_PUBLIC_KEY,
            "configured": True,
        }
        diagnostic = await client.get("/api/push/debug")
        assert diagnostic.status_code == 200
        assert diagnostic.json()["debug"]["configuration_status"]["vapid_configured"]
        result = await client.post("/api/push/test")
        assert result.status_code == 200
        assert "No active push subscriptions" in result.json()["message"]


def seed_media(apps, databases):
    paths = []
    for index, (app, db) in enumerate(zip(apps, databases)):
        media = (
            Path(app.state.settings.RECORDING_DIRECTORY) / "Season 2026" / "owned.mp4"
        )
        media.parent.mkdir()
        media.write_bytes(b"x" * (100 if index == 0 else 900))
        paths.append(media)
        with db.sync_session_factory() as session:
            session.add(
                Stream(
                    id=4,
                    streamer_id=1,
                    title="owned",
                    recording_path=str(media),
                    started_at=datetime.now(timezone.utc) - timedelta(days=10),
                    ended_at=datetime.now(timezone.utc) - timedelta(days=9),
                )
            )
            session.commit()
    return paths


@pytest.mark.asyncio
async def test_storage_and_custom_cleanup_are_owned_off_loop(
    image_applications, monkeypatch
):
    apps, databases, clients, queries = image_applications
    cleanup = importlib.import_module("app.services.system.cleanup_service")
    config = importlib.import_module("app.config.settings")
    monkeypatch.setattr(cleanup, "SessionLocal", databases[1].sync_session_factory)
    monkeypatch.setattr(config, "get_settings", lambda: apps[1].state.settings)
    paths = seed_media(apps, databases)
    file_threads = []
    original_remove = cleanup.os.remove

    def remove(path, *args, **kwargs):
        if Path(path) in paths:
            file_threads.append(get_ident())
        return original_remove(path, *args, **kwargs)

    monkeypatch.setattr(cleanup.os, "remove", remove)
    queries.clear()
    response = await clients[0].get("/api/recording/storage/1")
    assert response.status_code == 200
    assert response.json()["totalSize"] == 100
    response = await clients[0].post(
        "/api/recording/cleanup/1/custom",
        json={
            "type": "age",
            "threshold": 1,
            "preserve_favorites": False,
            "preserve_categories": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1
    stream_queries = [thread for thread, sql in queries if "FROM streams" in sql]
    assert stream_queries and get_ident() not in stream_queries
    assert not paths[0].exists()
    assert paths[1].read_bytes() == b"x" * 900
    for db, exists in zip(databases, (False, True)):
        with db.sync_session_factory() as session:
            assert (session.get(Stream, 4) is not None) is exists
    assert file_threads and get_ident() not in file_threads


@pytest.mark.asyncio
async def test_periodic_cleanup_is_owned_and_cancellable(
    image_applications, monkeypatch
):
    apps, databases, _, queries = image_applications
    lifecycle = importlib.import_module("app.lifespan")
    paths = seed_media(apps, databases)
    with databases[0].sync_session_factory() as session:
        session.add(
            RecordingSettings(
                cleanup_policy='{"type":"age","threshold":1,"preserve_favorites":false}'
            )
        )
        session.commit()
    peer_queries = []

    def observe(*args):
        peer_queries.append(get_ident())

    event.listen(databases[1].sync_engine, "before_cursor_execute", observe)

    async def stop_after_one_cycle(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(lifecycle.asyncio, "sleep", stop_after_one_cycle)
    queries.clear()
    with pytest.raises(asyncio.CancelledError):
        await lifecycle._run_recording_cleanup(
            databases[0].sync_session_factory, apps[0].state.settings
        )
    assert not paths[0].exists()
    assert paths[1].read_bytes() == b"x" * 900
    assert not peer_queries
    assert queries and all(thread != get_ident() for thread, _ in queries)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.asyncio
async def test_retention_cancellation_drains_transaction(image_applications):
    apps, databases, _, _ = image_applications
    seed_media(apps, databases)
    entered, release = Event(), Event()

    def held_select(*args):
        if "FROM streams" in args[2]:
            entered.set()
            assert release.wait(5)

    event.listen(databases[0].sync_engine, "before_cursor_execute", held_select)
    service = CleanupService(
        session_factory=databases[0].sync_session_factory,
        settings=apps[0].state.settings,
    )
    task = asyncio.create_task(service.get_storage_usage(1))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert databases[0].sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,url,expected",
    [
        (False, "", "Notifications are disabled"),
        (True, "", "No notification URL configured"),
    ],
)
async def test_notification_validation_sql_is_off_loop(
    image_applications, enabled, url, expected
):
    _, databases, clients, queries = image_applications
    with databases[0].sync_session_factory() as session:
        session.add(
            GlobalSettings(id=1, notifications_enabled=enabled, notification_url=url)
        )
        session.commit()
    queries.clear()
    response = await clients[0].post("/api/settings/test-notification")
    assert response.status_code == 400
    assert response.json()["detail"] == expected
    threads = [thread for thread, sql in queries if "FROM global_settings" in sql]
    assert threads and get_ident() not in threads
    assert databases[0].sync_engine.pool.checkedout() == 0
