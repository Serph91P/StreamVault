"""The mounted force-start path must use its own Twitch API, including offline replies."""

from aiohttp import web
import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import (
    _close_application_logging,
    _close_application_proxy,
    _close_application_twitch,
)
from app.services.recording import recording_lifecycle_manager as lifecycle_module
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
async def test_force_start_offline_lookup_uses_factory_http_owner_and_releases_sql(
    image_applications, monkeypatch
):
    apps, databases, clients, _ = image_applications
    received, borrowed = [], []

    async def streams(request):
        owner = int(request.headers["Client-ID"].removeprefix("owned-"))
        assert databases[owner].sync_engine.pool.checkedout() == 0
        received.append((owner, request.query["user_id"]))
        return web.json_response({"data": []})

    async def forbidden_default(*_args, **_kwargs):
        borrowed.append(True)
        raise AssertionError("factory force start borrowed the default Twitch API")

    provider = web.Application()
    provider.router.add_get("/helix/streams", streams)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    base = f"http://127.0.0.1:{runner.addresses[0][1]}/helix"
    monkeypatch.setattr(lifecycle_module.twitch_api, "get_streams", forbidden_default)
    managers = []
    try:
        for index, app in enumerate(apps):
            app.state.settings.TWITCH_APP_ID = f"owned-{index}"
            api = await run_in_thread_pool(
                dependencies.get_application_twitch_api,
                HTTPConnection({"type": "http", "app": app}),
            )
            api.base_url = base
            api._access_token = "synthetic-local-token"
            api._token_expires_at = float("inf")
            manager = await run_in_thread_pool(
                dependencies.get_application_recording_manager,
                HTTPConnection({"type": "http", "app": app}),
            )
            managers.append(manager)
            response = await clients[index].post("/api/recording/force-start/1")
            assert response.status_code == 400
            assert manager.get_active_recordings() == {}
        assert received == [(0, "owner-0"), (1, "owner-1")]
        assert not borrowed
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for manager in managers:
            await manager.shutdown()
        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)
            await _close_application_logging(app)
        await runner.cleanup()
