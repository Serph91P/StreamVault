"""Actual local ntfy delivery verifies profile fallback and event-specific wire values."""

import json
from urllib.parse import parse_qs, urlsplit

from aiohttp import web
import pytest

from app.config.settings import Settings
from app.models import GlobalSettings, Streamer
from app.services.notifications.external_notification_service import (
    ExternalNotificationService,
)
from tests.test_external_notification_boundary import (
    notification_catalogs as notification_catalogs,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,event_type",
    [
        ("original", "offline"),
        ("details", "update"),
        ("current", "recording_started"),
        ("none", "recording_completed"),
        ("none", "recording_failed"),
        ("none", "other"),
    ],
)
async def test_ntfy_profile_configuration_priority_and_actual_event_tag(
    notification_catalogs, source, event_type, monkeypatch
):
    database = notification_catalogs[0]
    received = []

    async def receive(request):
        assert database.sync_engine.pool.checkedout() == 0
        received.append((dict(request.headers), await request.text()))
        return web.json_response({"id": "offline-fixture"})

    provider = web.Application()
    provider.router.add_post("/", receive)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    origin = f"http://127.0.0.1:{runner.addresses[0][1]}"
    avatar = origin + "/user-profile_image-300x300.png"
    try:
        with database.sync_session_factory() as session:
            settings = session.get(GlobalSettings, 1)
            settings.notification_url = origin.replace("http://", "ntfy://") + "/topic"
            settings.notify_recording_started = True
            settings.notify_recording_failed = True
            settings.notify_recording_completed = True
            streamer = session.get(Streamer, 1)
            streamer.profile_image_url = avatar if source == "current" else None
            streamer.original_profile_image_url = (
                avatar if source == "original" else None
            )
            session.commit()
        service = ExternalNotificationService(
            session_factory=database.sync_session_factory,
            settings=Settings(ENVIRONMENT="test", BASE_URL=origin, _env_file=None),
        )
        configured = []
        native_configuration = service._get_service_specific_url

        def observe_configuration(*args, **kwargs):
            url = native_configuration(*args, **kwargs)
            configured.append(parse_qs(urlsplit(url).query))
            return url

        monkeypatch.setattr(service, "_get_service_specific_url", observe_configuration)
        details = {"profile_image_url": avatar} if source == "details" else {}
        assert await service.send_stream_notification("channel", event_type, details)
        assert len(received) == 1
        headers, body = received[0]
        payload = json.loads(body)
        assert payload["topic"] == "topic"
        expected_tag = {
            "offline": "offline",
            "update": "update",
            "recording_started": "recording",
            "recording_completed": "recording_complete",
            "recording_failed": "recording_failed",
        }.get(event_type, "notification")
        assert headers["X-Tags"] == expected_tag
        assert len(configured) == 1
        if source != "none":
            assert configured[0]["avatar_url"] == [avatar.replace("300x300", "150x150")]
        else:
            assert "avatar_url" not in configured[0]
        # Existing image=no also suppresses ntfy's icon in pinned Apprise.
        # This verifies configuration priority, not avatar/device display.
        assert configured[0]["image"] == ["no"] and "X-Icon" not in headers
        assert headers["X-Click"] == "https://twitch.tv/channel"
    finally:
        await runner.cleanup()
