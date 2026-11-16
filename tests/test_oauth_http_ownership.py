"""OAuth exchange and follow projection use only their owner's managed transport."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from app.services.api.twitch_api import TwitchAPIService
from app.services.api.twitch_oauth_service import TwitchOAuthService
from app.services.http_client import HTTPPolicy, ManagedHTTPClient
from app.lifespan import _close_application_twitch
from tests import test_image_http_ownership, test_proxy_http_ownership

image_applications = test_image_http_ownership.image_applications
proxy_applications = test_proxy_http_ownership.proxy_applications


@asynccontextmanager
async def oauth_origin(payload, *, status=200, hold=None):
    seen = []

    async def exchange(request):
        seen.append(
            (request.transport, dict(await request.post()), dict(request.query))
        )
        if hold is not None:
            hold[0].set()
            await hold[1].wait()
        if isinstance(payload, bytes):
            return web.Response(body=payload, status=status)
        return web.json_response(payload, status=status)

    async def validate(request):
        return web.json_response(
            {
                "user_id": request.headers["Authorization"]
                .removeprefix("OAuth ")
                .removesuffix("-token")
            }
        )

    async def follows(request):
        return web.json_response(
            {
                "data": [
                    {
                        "broadcaster_id": "42",
                        "broadcaster_login": request.query["user_id"],
                    }
                ],
                "pagination": {},
            }
        )

    app = web.Application()
    app.router.add_post("/oauth2/token", exchange)
    app.router.add_get("/oauth2/validate", validate)
    app.router.add_get("/helix/channels/followed", follows)
    async with TestServer(app) as server:
        clients, apis, actors = [], [], []
        try:
            for index in range(2):
                config = SimpleNamespace(
                    TWITCH_APP_ID=f"fixture-id-{index}",
                    TWITCH_APP_SECRET=f"fixture-secret-{index}",
                    BASE_URL=f"https://owner-{index}.invalid",
                )
                http = ManagedHTTPClient(HTTPPolicy(max_response_bytes=1024))
                clients.append(http)
                native = http.request

                async def local(method, url, *, _native=native, **kwargs):
                    parsed = urlsplit(url)
                    assert parsed.hostname in {"id.twitch.tv", "api.twitch.tv"}
                    return await _native(
                        method, str(server.make_url(parsed.path)), **kwargs
                    )

                http.request = local
                api = TwitchAPIService(settings=config, http_client=http)
                apis.append(api)
                actors.append(
                    TwitchOAuthService(
                        settings=config, twitch_api=api, http_client=http
                    )
                )
            with patch(
                "aiohttp.ClientSession",
                side_effect=AssertionError("unmanaged external transport forbidden"),
            ):
                yield actors, apis, clients, seen
        finally:
            for actor in actors:
                await actor.close()
            for api in apis:
                await api.close()
            for http in clients:
                await http.close()


@pytest.mark.asyncio
async def test_oauth_exchange_pool_settings_and_follow_api_are_owner_local(caplog):
    payload = {
        "access_token": "fixture-access",
        "refresh_token": "fixture-refresh",
        "expires_in": 3600,
    }
    async with oauth_origin(payload) as (actors, apis, clients, seen):
        caplog.set_level("DEBUG")
        for index, actor in enumerate(actors):
            query = parse_qs(urlsplit(actor.get_auth_url("/settings")).query)
            assert query["client_id"] == [f"fixture-id-{index}"]
            assert query["redirect_uri"] == [
                f"https://owner-{index}.invalid/api/twitch/callback"
            ]
            assert query["state"] == ["/settings"]
            assert await actor.exchange_code("fixture-code") == payload
            assert await actor.exchange_code("fixture-code") == payload
            channels = await actor.get_user_followed_channels(f"owner-{index}-token")
            assert channels == [
                {
                    "id": "42",
                    "login": f"owner-{index}",
                    "display_name": None,
                    "followed_at": None,
                }
            ]
        assert len(seen) == 4
        assert seen[0][0] is seen[1][0]
        assert seen[2][0] is seen[3][0]
        assert seen[0][0] is not seen[2][0]
        for index, (_, form, query) in enumerate(seen):
            assert query == {}
            assert form == {
                "client_id": f"fixture-id-{index // 2}",
                "client_secret": f"fixture-secret-{index // 2}",
                "code": "fixture-code",
                "grant_type": "authorization_code",
                "redirect_uri": f"https://owner-{index // 2}.invalid/api/twitch/callback",
            }
        await actors[0].close()
        # Borrowed API/transport remain their application's responsibility.
        assert await apis[0].validate_token("still-usable") == {
            "user_id": "still-usable"
        }
        assert await actors[1].exchange_code("fixture-code") == payload
        assert all(
            s not in caplog.text
            for s in (
                "fixture-secret",
                "fixture-code",
                "fixture-access",
                "fixture-refresh",
                "owner-0-token",
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,status",
    [
        (b"fixture-private-body", 400),
        (b"fixture-private-body", 200),
        ([], 200),
        ({"access_token": True}, 200),
        (b"x" * 2048, 200),
        ({"access_token": "ok"}, 302),
    ],
)
async def test_oauth_exchange_rejects_failure_without_retry_or_private_diagnostics(
    payload, status, caplog
):
    async with oauth_origin(payload, status=status) as (actors, _, _, seen):
        assert await actors[0].exchange_code("fixture-code") is None
        assert len(seen) == 1
        assert "fixture-private-body" not in caplog.text
        assert "fixture-code" not in caplog.text


@pytest.mark.asyncio
async def test_oauth_exchange_preserves_request_cancellation():
    entered, release = asyncio.Event(), asyncio.Event()
    async with oauth_origin({"access_token": "ok"}, hold=(entered, release)) as (
        actors,
        _,
        _,
        seen,
    ):
        operation = asyncio.create_task(actors[0].exchange_code("fixture-code"))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
            assert len(seen) == 1
        finally:
            release.set()
            await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.asyncio
async def test_oauth_close_cancels_only_its_pending_exchange_and_prevents_reuse():
    entered, release = asyncio.Event(), asyncio.Event()
    async with oauth_origin({"access_token": "ok"}, hold=(entered, release)) as (
        actors,
        _,
        _,
        seen,
    ):
        pending = asyncio.create_task(actors[0].exchange_code("fixture-code"))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await actors[0].close()
            assert pending.done(), (
                "owned OAuth operation must drain before close returns"
            )
            with pytest.raises(asyncio.CancelledError):
                await pending
            with pytest.raises(RuntimeError, match="closed"):
                await actors[0].exchange_code("fixture-code")
            release.set()
            assert await actors[1].exchange_code("fixture-code") == {
                "access_token": "ok"
            }
            assert len(seen) == 2
        finally:
            release.set()
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_real_oauth_url_requests_have_no_streamer_session_and_use_own_settings(
    image_applications, monkeypatch
):
    applications, databases, clients, _ = image_applications
    from app import dependencies
    from app.routes.twitch_auth import get_twitch_oauth_service
    from starlette.requests import HTTPConnection

    async def forbidden_registry():
        raise AssertionError(
            "URL generation/follows must not initialize EventSub or borrow its database"
        )

    for index, app in enumerate(applications):
        app.state.settings.TWITCH_APP_ID = f"fixture-id-{index}"
        app.state.settings.BASE_URL = f"https://owner-{index}.invalid"
        app.dependency_overrides[dependencies.get_application_event_registry] = (
            forbidden_registry
        )
    try:
        for index, client in enumerate(clients):
            response = await client.get(
                "/api/twitch/auth-url", params={"state": "/settings"}
            )
            assert response.status_code == 200
            query = parse_qs(urlsplit(response.json()["auth_url"]).query)
            assert query["client_id"] == [f"fixture-id-{index}"]
            assert query["redirect_uri"] == [
                f"https://owner-{index}.invalid/api/twitch/callback"
            ]
            callback = await client.get("/api/twitch/callback-url")
            assert callback.json() == {
                "url": f"https://owner-{index}.invalid/api/twitch/callback"
            }
            assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        owners = [
            get_twitch_oauth_service(
                HTTPConnection({"type": "http", "app": app, "headers": []})
            )
            for app in applications
        ]
        assert owners[0] is not owners[1]
        assert owners[0]._http is not owners[1]._http
        assert all(owner._http._client is None for owner in owners)
        assert all(
            owner._twitch_api is app.state.twitch_api
            for owner, app in zip(owners, applications)
        )
        await _close_application_twitch(applications[0])
        assert applications[0].state.twitch_oauth_service is None
        assert applications[1].state.twitch_oauth_service is owners[1]
        with pytest.raises(RuntimeError, match="closed"):
            await owners[0].exchange_code("fixture-code")
    finally:
        for app in applications:
            await _close_application_twitch(app)
