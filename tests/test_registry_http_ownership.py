"""Registry subscription HTTP stays inside the injected Twitch owner and pool."""

import asyncio
import aiohttp

import pytest
from aiohttp import web
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.events import handler_registry as module
from app.main import create_app
from app.services.api.twitch_api import (
    TwitchAPIService,
    twitch_api as legacy_twitch_api,
)
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_external_notification_boundary import notification_catalogs as _catalogs

notification_catalogs = _catalogs


@pytest.mark.asyncio
async def test_registry_eventsub_and_user_http_use_only_their_injected_twitch_owner(
    notification_catalogs, monkeypatch, caplog
):
    applications, clients, registries = [], [], []
    seen = []
    created = []
    versions = {"stream.online": "1", "stream.offline": "1", "channel.update": "2"}
    state = {"reject": False, "rows": None}
    caplog.set_level("DEBUG", logger="streamvault")

    async def subscriptions(request):
        owner = request.headers["Client-ID"]
        assert (
            request.headers["Authorization"] == f"Bearer fixture-{owner}-private-token"
        )
        assert owner in {"first", "second"}
        seen.append((owner, request.method, request.query.get("id")))
        if state["reject"]:
            return web.json_response(
                {"message": "fixture-private-provider-secret"}, status=503
            )
        if request.method == "GET":
            return web.json_response(
                {
                    "data": state["rows"]
                    if state["rows"] is not None
                    else [{"id": f"{owner}-existing", "status": "enabled"}],
                    "pagination": {"cursor": "literal"},
                }
            )
        if request.method == "POST":
            payload = await request.json()
            created.append((owner, payload))
            assert payload["type"] in {
                "stream.online",
                "stream.offline",
                "channel.update",
            }
            if payload["version"] != versions[payload["type"]]:
                return web.json_response(
                    {"error": "unsupported event version"}, status=400
                )
            assert payload["condition"] == {"broadcaster_user_id": f"user-{owner}"}
            assert payload["transport"] == {
                "method": "webhook",
                "callback": f"https://{owner}.invalid/eventsub",
                "secret": f"fixture-{owner}-webhook",
            }
            return web.json_response({"data": []}, status=202)
        assert request.query["id"] == f"{owner}-existing"
        return web.Response(status=204)

    async def users(request):
        owner = request.headers["Client-ID"]
        assert (
            request.headers["Authorization"] == f"Bearer fixture-{owner}-private-token"
        )
        return web.json_response(
            {"data": [{"id": request.query["id"], "login": owner}]}
        )

    provider = web.Application()
    provider.router.add_route("*", "/helix/eventsub/subscriptions", subscriptions)
    provider.router.add_get("/helix/users", users)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]

    def forbidden_unmanaged(*args, **kwargs):
        raise AssertionError("Registry must not construct an unmanaged aiohttp session")

    monkeypatch.setattr(aiohttp, "ClientSession", forbidden_unmanaged)

    async def forbidden_default(*args, **kwargs):
        raise AssertionError("Registry must never call the default Twitch HTTP client")

    monkeypatch.setattr(legacy_twitch_api, "_request", forbidden_default)
    try:
        for name, database in zip(("first", "second"), notification_catalogs):
            settings = Settings(
                ENVIRONMENT="test",
                TWITCH_APP_ID=name,
                TWITCH_APP_SECRET="fixture",
                WEBHOOK_URL=f"https://{name}.invalid",
                EVENTSUB_SECRET=f"fixture-{name}-webhook",
                _env_file=None,
            )
            app = create_app(settings=settings, database=database)
            applications.append(app)
            recorder = await run_in_thread_pool(
                dependencies.get_application_recording_manager,
                HTTPConnection({"type": "http", "app": app, "headers": []}),
            )
            client = TwitchAPIService(settings=settings)
            client.base_url = f"http://127.0.0.1:{port}/helix"
            client._access_token = f"fixture-{name}-private-token"
            client._token_expires_at = float("inf")
            clients.append(client)
            registry = module.EventHandlerRegistry(
                app.state.websocket_manager,
                settings=settings,
                session_factory=database.sync_session_factory,
                recording_manager=recorder,
                notification_service=dependencies._get_application_notification_service(
                    app
                ),
                twitch_api=client,
            )
            registries.append(registry)
            await registry.initialize_eventsub()

        async def exercise(index, name):
            registry = registries[index]
            assert await registry.get_access_token() == f"fixture-{name}-private-token"
            await registry.subscribe_to_events(f"user-{name}")
            assert await registry.list_subscriptions() == {
                "data": [{"id": f"{name}-existing", "status": "enabled"}],
                "pagination": {"cursor": "literal"},
            }
            assert (
                await registry.verify_subscription(f"{name}-existing", max_attempts=2)
                is True
            )
            assert await registry.delete_subscription(f"{name}-existing") == {
                "id": f"{name}-existing",
                "status": "deleted",
            }
            assert await registry.get_user_info(f"user-{name}") == {
                "id": f"user-{name}",
                "login": name,
            }

        await asyncio.gather(exercise(0, "first"), exercise(1, "second"))
        assert sum(method == "POST" for _, method, _ in seen) == 6
        assert sum(method == "GET" for _, method, _ in seen) == 4
        assert sum(method == "DELETE" for _, method, _ in seen) == 2
        assert len(created) == 6
        assert {(owner, payload["type"]) for owner, payload in created} == {
            (owner, event_type)
            for owner in ("first", "second")
            for event_type in ("stream.online", "stream.offline", "channel.update")
        }
        for owner, payload in created:
            assert payload == {
                "type": payload["type"],
                "version": versions[payload["type"]],
                "condition": {"broadcaster_user_id": f"user-{owner}"},
                "transport": {
                    "method": "webhook",
                    "callback": f"https://{owner}.invalid/eventsub",
                    "secret": f"fixture-{owner}-webhook",
                },
            }
        first = registries[0]
        state["rows"] = [
            {
                "id": "first-existing",
                "condition": {"broadcaster_user_id": "user-first"},
                "type": "stream.online",
            }
        ]
        await first.unsubscribe_from_events("user-first")
        assert seen[-1] == ("first", "DELETE", "first-existing")
        assert await first.delete_all_subscriptions() == {
            "success": True,
            "results": [{"id": "first-existing", "status": "deleted"}],
        }
        for invalid in ("not-an-array", ["not-a-row"], [{"id": None}]):
            state["rows"] = invalid
            with pytest.raises(ValueError, match="Invalid EventSub"):
                await first.unsubscribe_from_events("user-first")
            with pytest.raises(ValueError, match="Invalid EventSub"):
                await first.delete_all_subscriptions()
        state["rows"] = []
        assert await first.verify_subscription("missing", max_attempts=1) is False
        before = len(seen)
        assert await first.verify_subscription("missing", max_attempts=0) is False
        assert len(seen) == before
        state["reject"] = True
        assert await first.list_subscriptions() == {"data": []}
        assert await first.delete_subscription("first-existing") == {
            "id": "first-existing",
            "status": "failed",
            "error": "Status code: 503",
        }
        await first.subscribe_to_events("user-first")
        assert len(seen) == before + 5, (
            "EventSub mutations must not acquire a new automatic retry policy"
        )
        state.update(reject=False, rows=None)
        await clients[0].close()
        assert await first.get_user_info("user-first") is None
        assert (await registries[1].list_subscriptions())["data"][0][
            "id"
        ] == "second-existing"
        assert "private-token" not in caplog.text
        assert "-webhook" not in caplog.text
        assert "fixture-private-provider-secret" not in caplog.text
    finally:
        for client in clients:
            await client.close()
        for app in applications:
            await app.state.websocket_manager.close_all()
        await runner.cleanup()
