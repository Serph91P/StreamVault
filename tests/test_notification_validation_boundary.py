"""Validation completes its worker transaction before notification delivery."""

import asyncio
from threading import get_ident

import pytest

from app import dependencies
from app.models import GlobalSettings
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
async def test_admin_orphan_cleanup_uses_own_root(image_applications, monkeypatch):
    from pathlib import Path
    import app.config.settings as config

    apps, _, clients, _ = image_applications
    monkeypatch.setattr(config, "get_settings", lambda: apps[1].state.settings)
    paths = [Path(app.state.settings.RECORDING_DIRECTORY) / "empty.nfo" for app in apps]
    for path in paths:
        path.touch()
    response = await clients[0].post(
        "/api/admin/post-processing/cleanup-orphaned-files"
    )
    assert response.status_code == 200
    assert response.json()["data"]["cleaned_count"] == 1
    assert not paths[0].exists()
    assert paths[1].exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "false", "error", "cancel"])
async def test_notification_transports_never_hold_validation_session(
    image_applications, monkeypatch, outcome
):
    apps, databases, clients, queries = image_applications
    db = databases[0]
    with db.sync_session_factory() as session:
        session.add(
            GlobalSettings(
                id=1, notifications_enabled=True, notification_url="json://127.0.0.1"
            )
        )
        session.commit()
    calls = []

    async def websocket(payload):
        assert db.sync_engine.pool.checkedout() == 0
        calls.append("websocket")
        assert payload["data"]["streamer_name"] == "TestUser"

    class Notification:
        async def send_test_notification(self):
            assert db.sync_engine.pool.checkedout() == 0
            calls.append("external")
            if outcome == "error":
                raise RuntimeError("synthetic transport failure")
            if outcome == "cancel":
                raise asyncio.CancelledError
            return outcome == "success"

    monkeypatch.setattr(apps[0].state.websocket_manager, "send_notification", websocket)
    apps[0].dependency_overrides[dependencies.get_notification_service_factory] = (
        lambda: Notification
    )
    queries.clear()
    if outcome == "cancel":
        from app.routes.settings import test_notification

        with pytest.raises(asyncio.CancelledError):
            await test_notification(
                db.sync_session_factory,
                Notification,
                apps[0].state.websocket_manager,
                None,
            )
    else:
        response = await clients[0].post("/api/settings/test-notification")
        assert response.status_code == (200 if outcome == "success" else 500)
    assert calls == ["websocket", "external"]
    threads = [thread for thread, sql in queries if "FROM global_settings" in sql]
    assert threads and get_ident() not in threads
    assert db.sync_engine.pool.checkedout() == 0
