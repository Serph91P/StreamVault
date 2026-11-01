"""Managed streaming is required by image staging, without buffering the body first."""

import asyncio

import pytest
from aiohttp import web

from tests.test_managed_http_client import server, types


@pytest.mark.asyncio
async def test_stream_preserves_headers_incremental_bytes_size_limit_and_capacity():
    Client, Policy, Error = types()
    released = asyncio.Event()
    seen = []

    async def chunks(request):
        seen.append(request.path)
        if request.path == "/ok":
            return web.Response(body=b"ok")
        response = web.StreamResponse(headers={"Content-Type": "image/jpeg"})
        await response.prepare(request)
        await response.write(b"abc")
        await released.wait()
        await response.write(b"def")
        return response

    app = web.Application()
    app.router.add_get("/{path}", chunks)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    url = f"http://127.0.0.1:{runner.addresses[0][1]}"
    client = Client(
        Policy(
            max_response_bytes=4,
            max_connections=1,
            max_keepalive_connections=1,
            pool_timeout=0.05,
        )
    )
    try:
        async with client.stream("GET", url + "/chunks") as reply:
            assert reply.status_code == 200
            assert reply.headers["content-type"] == "image/jpeg"
            assert await asyncio.wait_for(anext(reply.chunks), 1) == b"abc"
            assert not released.is_set(), "First bytes must not wait for full body"
            with pytest.raises(Error) as error:
                await client.request("GET", url + "/ok")
            assert error.value.code == "timeout"
            released.set()
            with pytest.raises(Error) as error:
                await anext(reply.chunks)
            assert error.value.code == "response_too_large"
            assert url not in str(error.value)
        assert (await client.request("GET", url + "/ok")).body == b"ok"
        assert seen == ["/chunks", "/ok"]
    finally:
        released.set()
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("path,status", [("redirect", 302), ("denied", 401)])
async def test_stream_status_policy_is_identical_to_buffered_requests(path, status):
    Client, Policy, Error = types()
    client = Client(Policy())
    try:
        async with server() as (url, seen, _, _):
            with pytest.raises(Error) as error:
                async with client.stream("GET", url + "/" + path):
                    pytest.fail("Rejected HTTP status must never expose a body")
            assert error.value.code == "status" and error.value.status_code == status
            assert [row[0] for row in seen] == ["/" + path]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_stream_cancellation_releases_its_pool_for_the_next_request():
    Client, Policy, Error = types()
    client = Client(Policy(max_connections=1, max_keepalive_connections=1))
    operation = None

    async def consume(url):
        async with client.stream("GET", url + "/slow") as reply:
            return [chunk async for chunk in reply.chunks]

    try:
        async with server() as (url, _, entered, release):
            operation = asyncio.create_task(consume(url))
            assert await asyncio.wait_for(entered.wait(), 5) is True
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
            release.set()
            assert (await client.request("GET", url + "/ok")).body == b"ok"
    finally:
        if operation is not None:
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["cancel", "timeout", "partial"])
async def test_stream_body_failure_or_cancellation_closes_the_actual_response(outcome):
    Client, Policy, Error = types()
    entered, release = asyncio.Event(), asyncio.Event()

    async def serve(request):
        if request.path == "/ok":
            return web.Response(body=b"ok")
        response = web.StreamResponse(headers={"Content-Length": "100"})
        await response.prepare(request)
        await response.write(b"abc")
        await release.wait()
        if outcome == "partial":
            request.transport.close()
        return response

    app = web.Application()
    app.router.add_get("/{path}", serve)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    url = f"http://127.0.0.1:{runner.addresses[0][1]}"
    client = Client(
        Policy(
            max_connections=1,
            max_keepalive_connections=1,
            read_timeout=0.05 if outcome == "timeout" else 5,
        )
    )

    async def consume():
        async with client.stream("GET", url + "/body") as reply:
            assert await anext(reply.chunks) == b"abc"
            entered.set()
            await anext(reply.chunks)

    operation = asyncio.create_task(consume())
    try:
        assert await asyncio.wait_for(entered.wait(), 5)
        if outcome == "cancel":
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
        else:
            if outcome == "partial":
                release.set()
            with pytest.raises(Error) as error:
                await operation
            assert error.value.code == (
                "timeout" if outcome == "timeout" else "network"
            )
            assert url not in str(error.value)
        assert (await client.request("GET", url + "/ok")).body == b"ok"
    finally:
        release.set()
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_stream_whole_operation_deadline_includes_its_consumer():
    Client, Policy, Error = types()
    client = Client(Policy(total_timeout=0.1))
    try:
        async with server() as (url, _, _, _):
            # Initialize CA/pool before the short deadline being tested.
            await client._get_client()
            with pytest.raises(Error) as error:
                async with client.stream("GET", url + "/ok") as reply:
                    assert reply.status_code == 200
                    await asyncio.sleep(1)
            assert error.value.code == "timeout"
    finally:
        await client.close()
