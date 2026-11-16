"""Native loopback HTTP policy/lifetime, not real-provider acceptance."""

import asyncio
import importlib
from contextlib import asynccontextmanager

import pytest
from aiohttp import web


def types():
    module = importlib.import_module("app.services.http_client")
    return module.ManagedHTTPClient, module.HTTPPolicy, module.HTTPClientError


@asynccontextmanager
async def server():
    seen = []
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        seen.append((request.path, request.transport, dict(request.headers)))
        if request.path == "/slow":
            entered.set()
            await release.wait()
        if request.path == "/redirect":
            raise web.HTTPFound("/ok")
        if request.path == "/denied":
            return web.Response(status=401, text="fixture-body-must-not-be-logged")
        if request.path == "/large":
            return web.Response(body=b"x" * 4096)
        response = web.Response(body=b"ok")
        response.set_cookie("fixture", "must-not-be-replayed")
        return response

    application = web.Application()
    application.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        yield f"http://127.0.0.1:{port}", seen, entered, release
    finally:
        release.set()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_http_owner_reuses_connections_but_never_cookies_or_peers():
    Client, Policy, Error = types()
    first, second = Client(Policy()), Client(Policy())
    try:
        async with server() as (url, seen, _, _):
            assert (
                await first.request("GET", url + "/ok", headers={"X-Owner": "first"})
            ).body == b"ok"
            assert (
                await first.request("GET", url + "/ok", headers={"X-Owner": "first"})
            ).status_code == 200
            await second.request("GET", url + "/ok", headers={"X-Owner": "second"})
            assert seen[0][1] is seen[1][1]
            assert seen[2][1] is not seen[1][1]
            assert [headers["X-Owner"] for _, _, headers in seen] == [
                "first",
                "first",
                "second",
            ]
            assert all("Cookie" not in headers for _, _, headers in seen)
            assert all("StreamVault" in headers["User-Agent"] for _, _, headers in seen)
            await first.close()
            with pytest.raises(Error, match="closed"):
                await first.request("GET", url + "/ok")
            assert (await second.request("GET", url + "/ok")).body == b"ok"
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,code,status",
    [
        ("large", "response_too_large", None),
        ("redirect", "status", 302),
        ("denied", "status", 401),
    ],
)
async def test_http_owner_bounds_responses_and_does_not_follow_or_log_errors(
    path, code, status, caplog
):
    Client, Policy, Error = types()
    client = Client(Policy(max_response_bytes=1024))
    try:
        async with server() as (url, seen, _, _):
            with pytest.raises(Error) as error:
                await client.request("GET", url + "/" + path)
            assert error.value.code == code
            assert error.value.status_code == status
            assert [entry[0] for entry in seen] == ["/" + path]
            assert "fixture-body-must-not-be-logged" not in caplog.text
            assert url not in str(error.value)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_http_owner_pool_timeout_and_cancellation_release_capacity():
    Client, Policy, Error = types()
    client = Client(
        Policy(max_connections=1, max_keepalive_connections=1, pool_timeout=0.05)
    )
    operation = None
    try:
        async with server() as (url, seen, entered, release):
            operation = asyncio.create_task(client.request("GET", url + "/slow"))
            await asyncio.wait_for(entered.wait(), 5)
            with pytest.raises(Error) as error:
                await client.request("GET", url + "/ok")
            assert error.value.code == "timeout"
            assert [entry[0] for entry in seen] == ["/slow"]
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
            release.set()
            assert (await client.request("GET", url + "/ok")).status_code == 200
    finally:
        if operation is not None and not operation.done():
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
        await client.close()


@pytest.mark.asyncio
async def test_http_owner_read_timeout_is_bounded():
    Client, Policy, Error = types()
    client = Client(Policy(read_timeout=0.05))
    try:
        async with server() as (url, _, _, release):
            with pytest.raises(Error) as error:
                await client.request("GET", url + "/slow")
            assert error.value.code == "timeout"
            release.set()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_http_total_deadline_is_independent_of_read_timeout():
    Client, Policy, Error = types()
    client = Client(Policy(total_timeout=0.05, read_timeout=5))
    try:
        async with server() as (url, seen, _, release):
            with pytest.raises(Error) as error:
                await asyncio.wait_for(client.request("GET", url + "/slow"), 1)
            assert error.value.code == "timeout"
            assert len(seen) == 1
            release.set()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_http_network_failure_is_typed_without_url_or_retry():
    import socket

    Client, Policy, Error = types()
    client = Client(Policy())
    # A bound non-listening socket supplies a reserved, refused local endpoint.
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{endpoint.getsockname()[1]}/credential-fixture"
        try:
            with pytest.raises(Error) as error:
                await client.request("POST", url, data={"token": "fixture"})
            assert error.value.code == "network"
            assert url not in str(error.value)
            assert error.value.__suppress_context__
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_http_ca_loading_is_off_loop_and_close_drains_repeated_cancellation(
    monkeypatch,
):
    import ssl
    import threading

    module = importlib.import_module("app.services.http_client")
    original_context = ssl.create_default_context
    loop_thread = threading.get_ident()
    context_threads = []

    def context():
        context_threads.append(threading.get_ident())
        return original_context()

    monkeypatch.setattr(module.ssl, "create_default_context", context)
    client = module.ManagedHTTPClient(module.HTTPPolicy())
    close_entered, release = asyncio.Event(), asyncio.Event()
    operation = None
    try:
        async with server() as (url, _, _, _):
            assert (await client.request("GET", url + "/ok")).body == b"ok"
        assert context_threads and all(t != loop_thread for t in context_threads)
        transport = client._client
        original_close = transport.aclose

        async def close():
            close_entered.set()
            await release.wait()
            await original_close()

        monkeypatch.setattr(transport, "aclose", close)
        operation = asyncio.create_task(client.close())
        await asyncio.wait_for(close_entered.wait(), 2)
        operation.cancel()
        await asyncio.sleep(0)
        operation.cancel()
        await asyncio.sleep(0)
        assert not operation.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation
        assert transport.is_closed
        await client.close()
    finally:
        release.set()
        if operation is not None:
            await asyncio.gather(operation, return_exceptions=True)
        await client.close()
