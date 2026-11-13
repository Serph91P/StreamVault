"""Online EventSub keeps catalog models inside workers and admission on its loop."""

import asyncio
import json
from datetime import datetime, timezone
from threading import get_ident

import pytest
from aiohttp import web
from sqlalchemy import event

from app.config.settings import Settings
from app.services.communication.websocket_manager import ConnectionManager
from app.events import handler_registry as module
from app.models import (
    RecordingSettings,
    StreamerRecordingSettings,
    Stream,
    Streamer,
    StreamEvent,
)
from app.services.api.twitch_api import TwitchAPIService
from tests.test_external_notification_boundary import notification_catalogs as _catalogs

notification_catalogs = _catalogs


@pytest.mark.asyncio
async def test_online_isolated_worker_snapshots_close_before_http_notify_and_admission(
    notification_catalogs, monkeypatch
):
    databases = notification_catalogs
    queries, received, notifications, admissions = [], [], [], []
    loop_thread = get_ident()
    registries, clients = [], []

    async def users(request):
        name = request.headers["Client-ID"]
        index = ("first", "second").index(name)
        assert databases[index].sync_engine.pool.checkedout() == 0
        received.append((name, request.query["id"]))
        return web.json_response(
            {
                "data": [
                    {
                        "id": name,
                        "profile_image_url": f"https://{name}.invalid/profile.jpg",
                        "description": name,
                    }
                ]
            }
        )

    provider = web.Application()
    provider.router.add_get("/helix/users", users)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        for index, (name, database) in enumerate(zip(("first", "second"), databases)):
            with database.sync_session_factory() as session:
                streamer = session.get(Streamer, 1)
                streamer.title, streamer.category_name, streamer.language = (
                    name,
                    "Games",
                    "de",
                )
                session.add(RecordingSettings(id=1, enabled=True))
                session.add(StreamerRecordingSettings(streamer_id=1, enabled=True))
                session.add(
                    Stream(
                        id=10,
                        streamer_id=1,
                        twitch_stream_id="old",
                        started_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
                    )
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *args: queries.append(get_ident()),
            )
            settings = Settings(ENVIRONMENT="test", TWITCH_APP_ID=name, _env_file=None)
            client = TwitchAPIService(settings=settings)
            client.base_url = f"http://127.0.0.1:{port}/helix"
            client._access_token, client._token_expires_at = (
                "fixture-token",
                float("inf"),
            )
            clients.append(client)

            class Notifications:
                def __init__(self, owner, database):
                    self.owner, self.database = owner, database

                async def send_stream_notification(self, **kwargs):
                    assert self.database.sync_engine.pool.checkedout() == 0
                    assert get_ident() == loop_thread
                    notifications.append((self.owner, json.loads(json.dumps(kwargs))))

            class Recorder:
                def __init__(self, owner, database):
                    self.owner, self.database = owner, database

                async def start_recording(self, stream_id, streamer_id, *, force_mode):
                    assert self.database.sync_engine.pool.checkedout() == 0
                    assert get_ident() == loop_thread
                    assert any(owner == self.owner for owner, _ in notifications)
                    admissions.append((self.owner, stream_id, streamer_id, force_mode))
                    return False  # The test observes admission, not a real provider capture.

            registries.append(
                module.EventHandlerRegistry(
                    ConnectionManager(),
                    settings=settings,
                    session_factory=database.sync_session_factory,
                    twitch_api=client,
                    recording_manager=Recorder(index, database),
                    notification_service=Notifications(index, database),
                )
            )

        def forbidden_default():
            raise AssertionError("Online events must not read the default catalog")

        monkeypatch.setattr(module, "SessionLocal", forbidden_default)
        payloads = [
            {
                "id": "new-stream",
                "broadcaster_user_id": name,
                "broadcaster_user_login": "channel",
                "broadcaster_user_name": "channel",
                "started_at": "2026-07-09T12:00:00Z",
            }
            for name in ("first", "second")
        ]
        await asyncio.gather(
            *(
                registry.handle_stream_online(payload)
                for registry, payload in zip(registries, payloads)
            )
        )
        assert len(admissions) == 2 and len(notifications) == 2
        assert sorted(received) == [("first", "first"), ("second", "second")]
        assert queries and loop_thread not in queries
        for index, database in enumerate(databases):
            with database.sync_session_factory() as session:
                stream = (
                    session.query(Stream)
                    .filter(Stream.twitch_stream_id == "new-stream")
                    .one()
                )
                assert stream.streamer_id == 1 and stream.ended_at is None
                assert stream.title == ("first", "second")[index]
                assert session.get(Stream, 10).ended_at is not None
                assert session.get(Streamer, 1).is_live is True
                assert (
                    session.get(Streamer, 1).description == ("first", "second")[index]
                )
                assert (
                    session.query(StreamEvent)
                    .filter(StreamEvent.stream_id == stream.id)
                    .count()
                    == 2
                )
                assert (index, stream.id, 1, False) in admissions
        # A rejected first admission remains retryable without another Stream or notification.
        await registries[0].handle_stream_online(payloads[0])
        assert len(admissions) == 3 and len(notifications) == 2
        with databases[0].sync_session_factory() as session:
            assert (
                session.query(Stream)
                .filter(Stream.twitch_stream_id == "new-stream")
                .count()
                == 1
            )
    finally:
        for client in clients:
            await client.close()
        for registry in registries:
            await registry.manager.close_all()
        await runner.cleanup()
