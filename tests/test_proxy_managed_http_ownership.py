"""Real loopback OAuth/proxy protocol, owning catalogues and shutdown effects."""

import asyncio
import importlib
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
import aiohttp
from aiohttp import web
from pydantic import SecretStr

from app.config.settings import Settings
from app.models import ProxySettings
from tests import test_proxy_identity_ownership

module = importlib.import_module("app.services.proxy.proxy_health_service")
proxy_databases = test_proxy_identity_ownership.proxy_databases


@asynccontextmanager
async def origin():
    seen = []
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        data = dict(await request.post()) if request.method == "POST" else {}
        seen.append(
            (
                request.path,
                request.transport,
                dict(request.headers),
                dict(request.query),
                data,
            )
        )
        if request.path == "/token":
            return web.json_response(
                {"access_token": "synthetic-token-" + data["client_id"]}
            )
        if request.path == "/hold":
            entered.set()
            await release.wait()
        return web.Response(body=b"ok")

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    try:
        yield f"http://127.0.0.1:{runner.addresses[0][1]}", seen, entered, release
    finally:
        release.set()
        await runner.cleanup()


def forbid_transient_client(*args, **kwargs):
    raise AssertionError("Legacy transient HTTP client used")


@pytest.mark.asyncio
async def test_real_proxy_operations_reuse_isolated_transports_and_body_credentials(
    proxy_databases, monkeypatch
):
    databases, _ = proxy_databases
    services, notices = [], []
    monkeypatch.setattr(aiohttp, "ClientSession", forbid_transient_client)
    async with origin() as (url, seen, _, _):
        try:
            for index, database in enumerate(databases):
                with database.sync_session_factory() as session:
                    session.get(ProxySettings, 1).proxy_url = url
                    session.commit()
                service = module.ProxyHealthService(
                    settings=Settings(
                        ENVIRONMENT="test",
                        TWITCH_APP_ID=f"owner-{index}",
                        TWITCH_APP_SECRET=SecretStr(f"synthetic-app-secret-{index}"),
                        _env_file=None,
                    ),
                    session_factory=database.sync_session_factory,
                    websocket_manager=SimpleNamespace(
                        send_notification=_append_notice(notices)
                    ),
                )
                services.append(service)
                service.token_endpoint = url + "/token"
                service.test_endpoint = "http://upstream.invalid/health"
                for _ in range(2):
                    result = await service.check_proxy_health_manual(1)
                    assert result["health_status"] == "healthy", result
                own = seen[-4:]
                assert [entry[0] for entry in own] == [
                    "/token",
                    "/health",
                    "/token",
                    "/health",
                ]
                assert own[0][1] is own[2][1] and own[1][1] is own[3][1]
                assert own[0][1] is not own[1][1]
                assert all(entry[3] == {} for entry in own)
                assert own[0][4] == {
                    "client_id": f"owner-{index}",
                    "client_secret": f"synthetic-app-secret-{index}",
                    "grant_type": "client_credentials",
                }
                assert (
                    own[1][2]["Authorization"]
                    == f"Bearer synthetic-token-owner-{index}"
                )
                assert all("Cookie" not in entry[2] for entry in own)
            assert seen[0][1] is not seen[4][1]
            assert seen[1][1] is not seen[5][1]
            await services[0].stop()
            assert (await services[1].check_proxy_health_manual(1))[
                "health_status"
            ] == "healthy"
            assert len(notices) == 5
        finally:
            for service in services:
                await service.stop()


def _append_notice(notices):
    async def send(message):
        notices.append(message)

    return send


@pytest.mark.asyncio
async def test_shutdown_cancels_real_inflight_manual_http_and_retains_catalogue(
    proxy_databases, monkeypatch
):
    databases, _ = proxy_databases
    database = databases[0]
    monkeypatch.setattr(aiohttp, "ClientSession", forbid_transient_client)
    service = module.ProxyHealthService(
        settings=Settings(
            ENVIRONMENT="test",
            TWITCH_APP_ID="owner",
            TWITCH_APP_SECRET=SecretStr("synthetic-app-secret"),
            _env_file=None,
        ),
        session_factory=database.sync_session_factory,
    )
    task = None
    async with origin() as (url, _, entered, release):
        with database.sync_session_factory() as session:
            session.get(ProxySettings, 1).proxy_url = url
            session.commit()
        service.token_endpoint = url + "/token"
        service.test_endpoint = "http://upstream.invalid/hold"
        try:
            task = asyncio.create_task(service.check_proxy_health_manual(1))
            assert await asyncio.wait_for(entered.wait(), 2)
            await asyncio.wait_for(service.stop(), 2)
            with pytest.raises(asyncio.CancelledError):
                await task
            assert service._supervisor.closed and not service._supervisor.task_names
            with database.sync_session_factory() as session:
                row = session.get(ProxySettings, 1)
                assert row.health_status == "unknown" and row.last_health_check is None
            with pytest.raises(RuntimeError):
                await service.check_proxy_health_manual(1)
        finally:
            release.set()
            if task is not None and not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            await service.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["selection", "stats", "transport"])
async def test_stopped_proxy_actor_cannot_reopen_transport_or_use_database(
    operation, proxy_databases
):
    databases, _ = proxy_databases
    database = databases[0]
    service = module.ProxyHealthService(
        settings=Settings(ENVIRONMENT="test", _env_file=None),
        session_factory=database.sync_session_factory,
    )
    await service.stop()
    try:
        with pytest.raises(RuntimeError):
            if operation == "selection":
                await service.get_best_proxy()
            elif operation == "stats":
                await service.increment_recording_stats(
                    "http://owner-0:synthetic-password@proxy.invalid:8080", False
                )
            else:
                await service._proxy_transport("http://127.0.0.1:1")
        assert not service._proxy_clients
        with database.sync_session_factory() as session:
            assert session.get(ProxySettings, 1).total_recordings == 0
    finally:
        await service.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["id", "secret"])
async def test_missing_proxy_health_credentials_never_issue_token_http(missing):
    settings = Settings(
        ENVIRONMENT="test",
        TWITCH_APP_ID="" if missing == "id" else "owner",
        TWITCH_APP_SECRET=SecretStr(
            "" if missing == "secret" else "synthetic-app-secret"
        ),
        _env_file=None,
    )
    service = module.ProxyHealthService(settings=settings)
    async with origin() as (url, seen, _, _):
        service.token_endpoint = url + "/token"
        try:
            assert await service._get_twitch_access_token() is None
            assert seen == []
        finally:
            await service.stop()


@pytest.mark.asyncio
async def test_proxy_pool_eviction_and_stop_close_actual_connection_owners():
    service = module.ProxyHealthService(
        settings=Settings(
            ENVIRONMENT="test",
            TWITCH_APP_ID="owner",
            TWITCH_APP_SECRET=SecretStr("synthetic-app-secret"),
            _env_file=None,
        )
    )
    clients = []
    async with origin() as (url, seen, _, _):
        service.test_endpoint = "http://upstream.invalid/health"
        try:
            for index in range(service._proxy_capacity + 1):
                address = url.replace(
                    "http://", f"http://owner-{index}:synthetic-password@"
                )
                assert (await service._check_proxy_health(address, "synthetic-token"))[
                    "status"
                ] == "healthy"
                clients.append(service._proxy_clients[address])
                assert len(service._proxy_clients) <= service._proxy_capacity
            assert clients[0]._closed and clients[0]._client.is_closed
            assert len(seen) == service._proxy_capacity + 1
            await service.stop()
            assert not service._proxy_clients
            assert all(
                client._closed and client._client.is_closed for client in clients
            )
        finally:
            await service.stop()


@pytest.mark.asyncio
async def test_repeated_shutdown_cancellation_still_closes_every_pool(monkeypatch):
    service = module.ProxyHealthService(
        settings=Settings(
            ENVIRONMENT="test",
            TWITCH_APP_ID="owner",
            TWITCH_APP_SECRET=SecretStr("synthetic-app-secret"),
            _env_file=None,
        )
    )
    entered, release = asyncio.Event(), asyncio.Event()
    stop = None
    async with origin() as (url, _, _, _):
        service.token_endpoint = url + "/token"
        service.test_endpoint = "http://upstream.invalid/health"
        try:
            assert await service._get_twitch_access_token() == "synthetic-token-owner"
            assert (await service._check_proxy_health(url, "synthetic-token"))[
                "status"
            ] == "healthy"
            clients = [service._token_http, *service._proxy_clients.values()]
            native_close = service._token_http._client.aclose

            async def held_close():
                entered.set()
                await release.wait()
                await native_close()

            monkeypatch.setattr(service._token_http._client, "aclose", held_close)
            stop = asyncio.create_task(service.stop())
            await asyncio.wait_for(entered.wait(), 2)
            with pytest.raises(RuntimeError, match="stopping"):
                await service.start()
            stop.cancel()
            await asyncio.sleep(0)
            stop.cancel()
            await asyncio.sleep(0.02)
            assert not stop.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await stop
            assert not service._proxy_clients
            assert all(
                client._closed and client._client.is_closed for client in clients
            )
        finally:
            release.set()
            if stop is not None and not stop.done():
                await stop
            await service.stop()
