"""channel.update owns SQL snapshots before managed HTTP/image/notification awaits."""

import json
from datetime import datetime, timezone
from threading import get_ident

import pytest
from aiohttp import web
from sqlalchemy import event

from app.config.settings import Settings
from app.services.communication.websocket_manager import ConnectionManager
from app.events import handler_registry as module
from app.models import Category, Stream, StreamEvent, Streamer
from app.services.api.twitch_api import TwitchAPIService
from app.services.unified_image_service import UnifiedImageService
from tests import test_external_notification_boundary

notification_catalogs = test_external_notification_boundary.notification_catalogs


@pytest.mark.asyncio
async def test_channel_update_closes_owned_catalogues_before_external_awaits(
    notification_catalogs, tmp_path, monkeypatch
):
    databases = notification_catalogs
    queries, received, notifications = [], [], []
    clients, images, registries = [], [], []

    async def games(request):
        name = request.headers["Client-ID"]
        index = ("first", "second").index(name)
        assert databases[index].sync_engine.pool.checkedout() == 0
        received.append((name, request.query["id"]))
        return web.json_response(
            {"data": [{"id": "game", "name": name, "box_art_url": base + "/image"}]}
        )

    async def image(request):
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        return web.Response(body=b"owned-category-bytes", content_type="image/jpeg")

    provider = web.Application()
    provider.router.add_get("/helix/games", games)
    provider.router.add_get("/image", image)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    base = f"http://127.0.0.1:{runner.addresses[0][1]}"
    try:
        for index, (name, database) in enumerate(
            zip(("first", "second"), databases, strict=True)
        ):
            with database.sync_session_factory() as session:
                session.add(
                    Stream(id=10, streamer_id=1, started_at=datetime.now(timezone.utc))
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            settings = Settings(
                ENVIRONMENT="test",
                TWITCH_APP_ID=name,
                RECORDING_DIRECTORY=str(tmp_path / name),
                _env_file=None,
            )
            client = TwitchAPIService(settings=settings)
            client.base_url = base + "/helix"
            client._access_token, client._token_expires_at = (
                "fixture-token",
                float("inf"),
            )
            clients.append(client)
            facade = UnifiedImageService(
                settings=settings, session_factory=database.sync_session_factory
            )
            images.append(facade)

            class Notifications:
                def __init__(self, owner):
                    self.owner = owner

                async def send_stream_notification(self, **kwargs):
                    assert databases[self.owner].sync_engine.pool.checkedout() == 0
                    notifications.append((self.owner, json.loads(json.dumps(kwargs))))

            registries.append(
                module.EventHandlerRegistry(
                    ConnectionManager(),
                    settings=settings,
                    session_factory=database.sync_session_factory,
                    twitch_api=client,
                    recording_manager=object(),
                    notification_service=Notifications(index),
                    image_service=facade,
                )
            )

        # The old global implementation must not accidentally use either fixture DB.
        def forbidden_default():
            raise AssertionError("channel.update borrowed the process catalogue")

        monkeypatch.setattr(module, "SessionLocal", forbidden_default)
        for index, registry in enumerate(registries):
            await registry.handle_stream_update(
                {
                    "broadcaster_user_id": ("first", "second")[index],
                    "broadcaster_user_login": "channel",
                    "title": "new-title",
                    "language": "de",
                    "category_id": "game",
                }
            )
            assert notifications[-1][0] == index
            assert notifications[-1][1]["event_type"] == "update"
            assert (
                notifications[-1][1]["details"]["category_name"]
                == ("first", "second")[index]
            )
            assert queries and get_ident() not in queries
            queries.clear()
            with databases[index].sync_session_factory() as session:
                assert session.get(Streamer, 1).title == "new-title"
                assert (
                    session.get(Stream, 10).category_name == ("first", "second")[index]
                )
                assert session.query(StreamEvent).one().event_type == "channel.update"
                category = session.query(Category).one()
                assert category.name == ("first", "second")[index]
                assert category.box_art_url.startswith("/api/media/categories/")
            assert (
                images[index].categories_dir / (("first", "second")[index] + ".jpg")
            ).read_bytes() == b"owned-category-bytes"
            queries.clear()
            if index == 0:
                with databases[1].sync_session_factory() as session:
                    assert session.get(Streamer, 1).title != "new-title"
                    assert session.query(StreamEvent).count() == 0
                    assert session.query(Category).count() == 0
                queries.clear()
        assert {name for name, _ in received} == {"first", "second"}
    finally:
        for client in clients:
            await client.close()
        for facade in images:
            await facade.close()
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("favorites", [False, True])
async def test_update_existing_category_retains_art_and_favorite_wire_contract(
    notification_catalogs, favorites
):
    from types import SimpleNamespace
    from app.models import FavoriteCategory, NotificationSettings, User

    database = notification_catalogs[0]
    with database.sync_session_factory() as session:
        session.add(
            Category(id=4, twitch_id="game", name="old", box_art_url="/kept.jpg")
        )
        session.add_all(
            [
                User(id=1, username="one", password="unused"),
                User(id=2, username="two", password="unused"),
            ]
        )
        session.flush()
        session.add_all(
            [FavoriteCategory(user_id=identity, category_id=4) for identity in (1, 2)]
        )
        session.add(
            NotificationSettings(streamer_id=1, notify_favorite_category=favorites)
        )
        session.commit()
    sent = []

    async def send(**kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        sent.append(json.loads(json.dumps(kwargs)))

    async def forbidden_http(*_):
        pytest.fail("Existing named categories must not create provider work")

    registry = module.EventHandlerRegistry(
        ConnectionManager(),
        session_factory=database.sync_session_factory,
        recording_manager=object(),
        notification_service=SimpleNamespace(send_stream_notification=send),
        twitch_api=SimpleNamespace(get_games_by_id=forbidden_http),
    )
    await registry.handle_stream_update(
        {
            "broadcaster_user_id": "first",
            "broadcaster_user_login": "channel",
            "category_id": "game",
            "category_name": "new",
            "title": "new",
            "language": "de",
        }
    )
    assert [item["event_type"] for item in sent] == ["update"] + (
        ["favorite_category"] * 2 if favorites else []
    )
    for favorite in sent[1:]:
        assert set(favorite["details"]) == {
            "url",
            "title",
            "category_name",
            "language",
            "profile_image_url",
            "twitch_login",
        }
    with database.sync_session_factory() as session:
        category = session.get(Category, 4)
        assert category.name == "new" and category.box_art_url == "/kept.jpg"
        assert category.last_seen is not None
        assert session.query(StreamEvent).count() == 0


@pytest.mark.asyncio
async def test_unknown_update_has_no_provider_or_notification_effect(
    notification_catalogs,
):
    from types import SimpleNamespace

    async def forbidden(*args, **kwargs):
        pytest.fail("Unknown broadcasters cannot reach external services")

    registry = module.EventHandlerRegistry(
        ConnectionManager(),
        session_factory=notification_catalogs[0].sync_session_factory,
        recording_manager=object(),
        notification_service=SimpleNamespace(send_stream_notification=forbidden),
        twitch_api=SimpleNamespace(get_games_by_id=forbidden),
    )
    await registry.handle_stream_update(
        {"broadcaster_user_id": "unknown", "category_id": "game"}
    )
    with notification_catalogs[0].sync_session_factory() as session:
        assert session.query(Category).count() == 0
        assert session.query(StreamEvent).count() == 0
