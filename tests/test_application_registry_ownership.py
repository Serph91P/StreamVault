"""Real signed callbacks resolve the factory registry and its own signing key."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.main import create_app
from app.models import GlobalSettings, Stream, StreamEvent, Streamer
from app.lifespan import _close_application_images, _close_application_twitch
from tests import test_external_notification_boundary

notification_catalogs = test_external_notification_boundary.notification_catalogs


@pytest.mark.asyncio
async def test_factory_registries_and_signed_callbacks_never_borrow_peer_state(
    notification_catalogs, tmp_path, caplog, monkeypatch
):
    applications, registries = [], []
    try:
        for index, database in enumerate(notification_catalogs):
            with database.sync_session_factory() as session:
                session.get(GlobalSettings, 1).notifications_enabled = False
                session.add(
                    Stream(id=10, streamer_id=1, started_at=datetime.now(timezone.utc))
                )
                session.commit()
            settings = Settings(
                ENVIRONMENT="test",
                EVENTSUB_SECRET=f"synthetic-owner-{index}",
                RECORDING_DIRECTORY=str(tmp_path / f"owner-{index}"),
                _env_file=None,
            )
            app = create_app(settings=settings, database=database)
            applications.append(app)
            assert app.state.event_registry is None
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            candidates = await asyncio.gather(
                *(
                    dependencies.get_application_event_registry(connection)
                    for _ in range(3)
                )
            )
            registry = candidates[0]
            registries.append(registry)
            assert all(candidate is registry for candidate in candidates)
            assert registry is app.state.event_registry
            assert registry.manager is app.state.websocket_manager
            assert registry.recording_service is app.state.recording_manager
            assert registry.notification_service is app.state.notification_service
            assert registry.twitch_api is app.state.twitch_api
            assert registry._image_service is app.state.image_service
        assert registries[0] is not registries[1]
        for index, app in enumerate(applications):
            payload = {
                "subscription": {"type": "channel.update"},
                "event": {
                    "broadcaster_user_id": ("first", "second")[index],
                    "broadcaster_user_login": "channel",
                    "title": f"signed-{index}",
                    "language": "de",
                    "category_name": "Games",
                },
            }
            body = json.dumps(payload).encode()
            timestamp = datetime.now(timezone.utc).isoformat()
            message = b"same-message" + timestamp.encode() + body
            headers = {
                "Twitch-Eventsub-Message-Id": "same-message",
                "Twitch-Eventsub-Message-Timestamp": timestamp,
                "Twitch-Eventsub-Message-Type": "notification",
                "Twitch-Eventsub-Message-Signature": "sha256="
                + hmac.new(
                    app.state.settings.EVENTSUB_SECRET.encode(), message, hashlib.sha256
                ).hexdigest(),
            }
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://localhost:8000",
            ) as client:
                invalid = dict(headers)
                invalid["Twitch-Eventsub-Message-Signature"] = (
                    "sha256="
                    + hmac.new(
                        applications[1 - index].state.settings.EVENTSUB_SECRET.encode(),
                        message,
                        hashlib.sha256,
                    ).hexdigest()
                )
                assert (
                    await client.post("/eventsub", content=body, headers=invalid)
                ).status_code == 403
                assert (
                    invalid["Twitch-Eventsub-Message-Signature"][:16] not in caplog.text
                )
                assert (
                    headers["Twitch-Eventsub-Message-Signature"][:16] not in caplog.text
                )
                assert (
                    await client.post("/eventsub", content=body, headers=headers)
                ).status_code == 204
                assert (
                    await client.post("/eventsub", content=body, headers=headers)
                ).status_code == 204
            with notification_catalogs[index].sync_session_factory() as session:
                assert session.get(Streamer, 1).title == f"signed-{index}"
                assert session.query(StreamEvent).count() == 1
            if index == 0:
                with notification_catalogs[1].sync_session_factory() as session:
                    assert session.query(StreamEvent).count() == 0
        assert all(
            database.sync_engine.pool.checkedout() == 0
            for database in notification_catalogs
        )
        from types import SimpleNamespace
        from app.lifespan import lifespan
        from app.services.system.migration_service import MigrationService

        monkeypatch.setattr(
            MigrationService,
            "for_engine",
            lambda _: SimpleNamespace(run_safe_migrations=lambda: False),
        )
        with pytest.raises(RuntimeError, match="migrations"):
            async with lifespan(applications[0]):
                pytest.fail("Faulted startup cannot become ready")
        assert applications[0].state.event_registry is None
        assert applications[1].state.event_registry is registries[1]
    finally:
        for app in applications:
            await _close_application_images(app)
            await _close_application_twitch(app)
            await app.state.websocket_manager.close_all()
