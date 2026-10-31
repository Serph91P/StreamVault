"""Real Helix client against a loopback-only synthetic HTTP provider."""

import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web
import pytest
import pytest_asyncio

from app.services.api import twitch_api as module
from app.utils.retry_decorator import NonRetryableError


@pytest_asyncio.fixture
async def provider(monkeypatch):
    state = SimpleNamespace(
        posts=0,
        headers=[],
        token_status=200,
        payload={"access_token": "synthetic-fresh", "expires_in": 3600},
        reject_fresh=False,
        status=200,
        stale_barrier=None,
        delay_second_stale=False,
        token_started=asyncio.Event(),
        token_release=None,
    )

    async def token(request):
        assert request.query["grant_type"] == "client_credentials"
        assert request.query["client_id"] == "synthetic-id"
        assert request.query["client_secret"] in {"synthetic-secret", ""}
        state.posts += 1
        state.token_started.set()
        if state.token_release is not None:
            await state.token_release.wait()
        return web.json_response(state.payload, status=state.token_status)

    async def helix(request):
        header = request.headers["Authorization"]
        state.headers.append(header)
        if header == "Bearer synthetic-stale":
            if state.stale_barrier is not None and (
                not state.delay_second_stale or len(state.headers) == 2
            ):
                await state.stale_barrier.wait()
            return web.json_response({"message": "synthetic-stale"}, status=401)
        if state.reject_fresh:
            return web.json_response({"message": "synthetic-fresh"}, status=401)
        return web.json_response({"data": [{"id": "42"}]}, status=state.status)

    app = web.Application()
    app.router.add_post("/oauth2/token", token)
    app.router.add_get("/helix/{path:.*}", helix)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    real_session = aiohttp.ClientSession

    def local_session(*args, **kwargs):
        session = real_session(*args, **kwargs)
        original_request = session._request

        async def local_request(method, url, **options):
            parsed = urlsplit(str(url))
            assert parsed.hostname in {"api.twitch.tv", "id.twitch.tv"}
            return await original_request(
                method, f"http://127.0.0.1:{port}{parsed.path}", **options
            )

        session._request = local_request
        return session

    monkeypatch.setattr(module.aiohttp, "ClientSession", local_session)
    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            TWITCH_APP_ID="synthetic-id", TWITCH_APP_SECRET="synthetic-secret"
        ),
    )
    client = module.TwitchAPIService()
    try:
        yield client, state
    finally:
        if state.token_release is not None:
            state.token_release.set()
        await runner.cleanup()


APP_CALLS = [
    ("get_users_by_login", {"usernames": ["example"]}),
    ("get_users_by_id", {"user_ids": ["42"]}),
    ("get_games_by_name", {"game_names": ["Example"]}),
    ("get_games_by_id", {"game_ids": ["42"]}),
    ("get_streams", {"user_ids": ["42"]}),
    ("search_categories", {"query": "Example"}),
    ("get_top_games", {}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,kwargs", APP_CALLS)
async def test_revoked_token_refreshes_once_and_next_call_reuses_cache(
    provider, method, kwargs
):
    client, state = provider
    client._access_token = "synthetic-stale"
    client._token_expires_at = float("inf")
    call = getattr(client, method)
    assert await call(**kwargs) == [{"id": "42"}]
    assert await call(**kwargs) == [{"id": "42"}]
    assert state.posts == 1
    assert state.headers == [
        "Bearer synthetic-stale",
        "Bearer synthetic-fresh",
        "Bearer synthetic-fresh",
    ]
    assert client._access_token == "synthetic-fresh"


@pytest.mark.asyncio
async def test_expiry_safety_margin_refreshes_before_deadline(provider, monkeypatch):
    client, state = provider
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(module, "monotonic", lambda: clock.now, raising=False)
    assert await client.get_access_token() == "synthetic-fresh"
    clock.now = 3639.0
    assert await client.get_access_token() == "synthetic-fresh"
    assert state.posts == 1
    clock.now = 3641.0
    state.payload = {"access_token": "synthetic-next", "expires_in": 3600}
    assert await client.get_access_token() == "synthetic-next"
    assert state.posts == 2


@pytest.mark.asyncio
async def test_repeated_401_is_terminal_and_does_not_log_token(provider, caplog):
    client, state = provider
    client._access_token = "synthetic-stale"
    client._token_expires_at = float("inf")
    state.reject_fresh = True
    with pytest.raises(NonRetryableError, match="401"):
        await client.get_stream_by_user_id("42")
    assert state.posts == 1
    assert state.headers == ["Bearer synthetic-stale", "Bearer synthetic-fresh"]
    assert client._access_token is None
    assert "synthetic-stale" not in caplog.text
    assert "synthetic-fresh" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,status",
    [
        ({"message": "synthetic-secret"}, 401),
        ({"access_token": "synthetic-fresh"}, 200),
        ({"access_token": "", "expires_in": 3600}, 200),
        ({"access_token": "synthetic-fresh", "expires_in": 0}, 200),
        ([], 200),
        ({"message": "synthetic-secret"}, 400),
    ],
)
async def test_failed_refresh_does_not_poison_cache_or_loop(
    provider, caplog, payload, status
):
    client, state = provider
    client._access_token = "synthetic-stale"
    client._token_expires_at = float("inf")
    state.payload, state.token_status = payload, status
    with pytest.raises(NonRetryableError):
        await client.get_streams(user_ids=["42"])
    assert state.posts == 1
    assert state.headers == ["Bearer synthetic-stale"]
    assert client._access_token is None
    assert "synthetic-secret" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_concurrent_expiry_shares_success_or_failure(provider, failed):
    client, state = provider
    state.token_release = asyncio.Event()
    if failed:
        state.token_status = 401
    calls = [asyncio.create_task(client.get_access_token()) for _ in range(8)]
    await asyncio.wait_for(state.token_started.wait(), 2)
    state.token_release.set()
    results = await asyncio.wait_for(asyncio.gather(*calls, return_exceptions=True), 2)
    assert state.posts == 1
    if failed:
        assert all(isinstance(result, NonRetryableError) for result in results)
    else:
        assert results == ["synthetic-fresh"] * 8


@pytest.mark.asyncio
async def test_late_stale_401_cannot_discard_fresh_cache(provider):
    client, state = provider
    client._access_token = "synthetic-stale"
    client._token_expires_at = float("inf")
    state.stale_barrier = asyncio.Event()
    state.delay_second_stale = True
    first = asyncio.create_task(client.get_streams(user_ids=["42"]))
    second = asyncio.create_task(client.get_users_by_id(["42"]))

    async def both_arrived():
        while len(state.headers) < 2:
            await asyncio.sleep(0)

    await asyncio.wait_for(both_arrived(), 2)
    assert await asyncio.wait_for(first, 2) == [{"id": "42"}]
    state.stale_barrier.set()
    assert (
        await asyncio.wait_for(asyncio.gather(first, second), 2) == [[{"id": "42"}]] * 2
    )
    assert state.posts == 1
    assert client._access_token == "synthetic-fresh"


@pytest.mark.asyncio
async def test_missing_configuration_fails_without_provider_request(provider):
    client, state = provider
    client.client_secret = ""
    with pytest.raises(NonRetryableError):
        await client.get_streams(user_ids=["42"])
    assert state.posts == 0
    assert state.headers == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 404, 500])
@pytest.mark.parametrize("method,kwargs", APP_CALLS)
async def test_non_auth_errors_keep_existing_retry_and_fallback_contract(
    provider, monkeypatch, status, method, kwargs
):
    client, state = provider
    state.status = status
    real_sleep = asyncio.sleep

    async def no_backoff(delay):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", no_backoff)
    call = getattr(client, method)
    if method in {"get_games_by_id", "search_categories", "get_top_games"}:
        assert await call(**kwargs) == []
        assert len(state.headers) == 1
    else:
        error = ConnectionError if status == 500 else NonRetryableError
        with pytest.raises(error, match=str(status)):
            await call(**kwargs)
        assert len(state.headers) == (3 if status == 500 else 1)
    assert state.posts == 1


@pytest.mark.asyncio
async def test_token_endpoint_transient_failure_keeps_three_attempt_budget(
    provider, monkeypatch
):
    client, state = provider
    state.token_status = 503
    real_sleep = asyncio.sleep

    async def no_backoff(delay):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", no_backoff)
    with pytest.raises(ConnectionError, match="503"):
        await client.get_access_token()
    assert state.posts == 3
    assert client._access_token is None
    assert state.headers == []


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_refresh(provider):
    client, state = provider
    state.token_release = asyncio.Event()
    first = asyncio.create_task(client.get_access_token())
    await asyncio.wait_for(state.token_started.wait(), 2)
    second = asyncio.create_task(client.get_access_token())
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    state.token_release.set()
    assert await asyncio.wait_for(second, 2) == "synthetic-fresh"
    assert await client.get_streams(user_ids=["42"]) == [{"id": "42"}]
    assert state.posts == 1


@pytest.mark.asyncio
async def test_user_token_rejection_never_refreshes_app_token(provider):
    client, state = provider
    assert await client.get_user_followed_streamers("42", "synthetic-stale") == []
    assert state.posts == 0
    assert client._access_token is None
