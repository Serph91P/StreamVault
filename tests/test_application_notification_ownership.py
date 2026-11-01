"""Real factory notification composition: owned catalog, WS, Apprise and TLS push."""

import asyncio
from threading import get_ident

import jwt
import pytest
from aiohttp import web
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.main import create_app
from app.models import GlobalSettings
from app.services.notification_service import NotificationService
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_external_notification_boundary import notification_catalogs as _catalogs
from tests.test_push_notification_boundary import owned_services
from tests.test_webpush_delivery import receiver as _tls_receiver

notification_catalogs = _catalogs
receiver = _tls_receiver


@pytest.mark.parametrize("original", [None, "https://images.invalid/original.jpg"])
def test_legacy_notification_url_wrapper_uses_actual_shared_helper_contract(original):
    service = NotificationService()
    url = service._get_service_specific_url(
        "ntfy://localhost/topic",
        "https://twitch.tv/channel",
        "",
        "channel",
        "online",
        original,
    )
    assert (
        url
        == "ntfy://localhost/topic?click=https://twitch.tv/channel&priority=high&tags=live&image=no"
    )


@pytest.mark.asyncio
async def test_two_factories_deliver_only_their_current_notification_policy(
    notification_catalogs, receiver, monkeypatch
):
    databases = notification_catalogs
    seeded, public_keys = owned_services(databases, receiver)
    applications, services, external = [], [], []
    queries = []
    loop_thread = get_ident()
    expected_owner = 0

    async def accept(request):
        owner = int(request.match_info["owner"])
        assert owner == expected_owner
        assert databases[owner].sync_engine.pool.checkedout() == 0
        external.append((owner, await request.json()))
        return web.Response(status=200)

    provider = web.Application()
    provider.router.add_post("/{owner}", accept)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]

    async def forbidden_legacy(*args, **kwargs):
        raise AssertionError("Factory notification must not use the default websocket")

    monkeypatch.setattr(
        dependencies.websocket_manager, "send_notification", forbidden_legacy
    )
    try:
        for index, database in enumerate(databases):
            with database.sync_session_factory() as session:
                session.get(
                    GlobalSettings, 1
                ).notification_url = f"json://127.0.0.1:{port}/{index}"
                session.commit()
            app = create_app(
                settings=seeded[index].push_service.settings, database=database
            )
            applications.append(app)
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            factory = dependencies.get_notification_service_factory(connection)
            candidates = await asyncio.gather(
                *(run_in_thread_pool(factory) for _ in range(3))
            )
            service = candidates[0]
            assert all(candidate is service for candidate in candidates)
            assert (
                service.dispatcher.push_service.push_service
                is not seeded[index].push_service
            )
            services.append(service)
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *args: queries.append(get_ident()),
            )
        assert services[0] is not services[1]
        details = {
            "streamer_id": 1,
            "stream_id": 7,
            "title": "factory title",
            "category_name": "Games",
        }
        await asyncio.gather(
            *(
                service.send_stream_notification("channel", "online", details)
                for service in services
            )
        )
        assert len(receiver["requests"]) == 1
        assert len(external) == 1 and external[0][0] == 0
        assert (
            external[0][1]["message"]
            == "Started streaming: factory title\nCategory: Games"
        )
        first_events = await applications[0].state.websocket_manager.get_events_since()
        assert (
            len(first_events) == 1
            and first_events[0]["data"]["title"] == "factory title"
        )
        assert await applications[1].state.websocket_manager.get_events_since() == []
        assert queries and loop_thread not in queries
        origin = receiver["subscription"]["endpoint"].split("/push/")[0]
        token = (
            receiver["requests"][0][1]["Authorization"].split("t=", 1)[1].split(",")[0]
        )
        jwt.decode(token, public_keys[0], algorithms=["ES256"], audience=origin)

        def switch():
            for index, database in enumerate(databases):
                with database.sync_session_factory() as session:
                    session.get(GlobalSettings, 1).notify_online_global = index == 1
                    session.commit()

        await run_in_thread_pool(switch)
        expected_owner = 1
        await applications[0].state.websocket_manager.close_all()
        await asyncio.gather(
            *(
                service.send_stream_notification("channel", "online", details)
                for service in services
            )
        )
        assert len(receiver["requests"]) == len(external) == 2
        assert external[-1][0] == 1
        assert (
            len(await applications[1].state.websocket_manager.get_events_since()) == 1
        )
        token = (
            receiver["requests"][-1][1]["Authorization"].split("t=", 1)[1].split(",")[0]
        )
        jwt.decode(token, public_keys[1], algorithms=["ES256"], audience=origin)
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for app in applications:
            await app.state.websocket_manager.close_all()
        await runner.cleanup()
