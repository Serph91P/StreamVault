"""Managed Twitch adapter uses native loopback HTTP, never real credentials."""

import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from aiohttp import web

from app.services.api.twitch_api import TwitchAPIService
from app.services.http_client import HTTPPolicy, ManagedHTTPClient
from app.utils.retry_decorator import NonRetryableError


@pytest.mark.asyncio
async def test_twitch_http_owner_uses_supplied_credentials_pool_and_bounded_body(
    caplog,
):
    seen = []

    async def token(request):
        form = await request.post()
        seen.append(("token", request.transport, dict(form), dict(request.query)))
        return web.json_response({"access_token": "fixture-token", "expires_in": 3600})

    async def streams(request):
        seen.append(("streams", request.transport, dict(request.headers), {}))
        if request.query.get("user_id") == "huge":
            return web.Response(body=b"x" * 2048)
        if request.query.get("user_id") == "malformed":
            return web.Response(body=b"credential-fixture-bad-json")
        if request.query.get("user_id") == "malformed-shape":
            return web.json_response({"data": ["not-an-object"]})
        return web.json_response({"data": [{"id": "42"}]})

    application = web.Application()
    application.router.add_post("/oauth2/token", token)
    application.router.add_get("/helix/streams", streams)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    http = ManagedHTTPClient(HTTPPolicy(max_response_bytes=1024))
    original_request = http.request

    async def local_request(method, url, **kwargs):
        parsed = urlsplit(url)
        assert parsed.hostname in {"api.twitch.tv", "id.twitch.tv"}
        return await original_request(
            method, f"http://127.0.0.1:{port}{parsed.path}", **kwargs
        )

    http.request = local_request
    client = None
    try:
        client = TwitchAPIService(
            settings=SimpleNamespace(
                TWITCH_APP_ID="owned-id", TWITCH_APP_SECRET="owned-secret"
            ),
            http_client=http,
        )
        caplog.set_level("INFO")
        assert await client.get_streams(user_ids=["42"]) == [{"id": "42"}]
        assert await client.get_streams(user_ids=["42"]) == [{"id": "42"}]
        assert len(seen) == 3
        assert all(item[1] is seen[0][1] for item in seen)
        assert seen[0][2] == {
            "client_id": "owned-id",
            "client_secret": "owned-secret",
            "grant_type": "client_credentials",
        }
        assert seen[0][3] == {}
        assert seen[1][2]["Client-ID"] == "owned-id"
        assert seen[1][2]["Authorization"] == "Bearer fixture-token"
        for user_id in ("huge", "malformed", "malformed-shape"):
            with pytest.raises(NonRetryableError):
                await client.get_streams(user_ids=[user_id])
        assert len(seen) == 6  # Oversized/malformed bodies are never retried.
        assert "owned-secret" not in caplog.text
        assert "fixture-token" not in caplog.text
        assert "credential-fixture-bad-json" not in caplog.text
        await client.close()
        with pytest.raises(NonRetryableError, match="closed"):
            await client.get_streams(user_ids=["42"])
    finally:
        if client is not None:
            await client.close()
        await http.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_twitch_owner_close_cancels_and_awaits_its_pending_refresh_only():
    first = TwitchAPIService()
    second = TwitchAPIService()
    entered = [asyncio.Event(), asyncio.Event()]
    released = [asyncio.Event(), asyncio.Event()]

    async def fetch(index):
        entered[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            released[index].set()

    first._fetch_access_token = lambda: fetch(0)
    second._fetch_access_token = lambda: fetch(1)
    operations = [
        asyncio.create_task(client.get_access_token()) for client in (first, second)
    ]
    try:
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered)), 2)
        await first.close()
        assert released[0].is_set() and not released[1].is_set()
        assert first._token_refresh.done()
        assert not second._token_refresh.done()
        assert first._token_refresh.get_name() == "streamvault:twitch-token-refresh"
        with pytest.raises(NonRetryableError, match="closed"):
            await first.get_access_token()
    finally:
        for client in (first, second):
            close = getattr(client, "close", None)
            if close is not None:
                await close()
        for operation in operations:
            operation.cancel()
        await asyncio.gather(*operations, return_exceptions=True)
