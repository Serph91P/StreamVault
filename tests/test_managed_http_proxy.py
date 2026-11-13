"""Loopback proxy protocol preserves managed bounds, privacy and owner pools."""

import asyncio
import logging

import pytest

from app.services.http_client import ManagedHTTPClient, HTTPPolicy, HTTPClientError
from tests.test_managed_http_client import server


@pytest.mark.asyncio
async def test_managed_proxy_clients_route_authenticate_pool_and_close_without_peer_effect(
    caplog,
):
    async with server() as (proxy, seen, _, _):
        address = proxy.replace("http://", "http://synthetic-user:synthetic-password@")
        first = ManagedHTTPClient(HTTPPolicy(), proxy=address)
        peer = ManagedHTTPClient(HTTPPolicy(), proxy=address)
        try:
            with caplog.at_level(logging.DEBUG):
                for client in (first, first, peer):
                    reply = await client.request(
                        "GET",
                        "http://origin.invalid/ok?token=synthetic-url-marker",
                        headers={"Authorization": "Bearer synthetic-access-marker"},
                    )
                    assert reply.body == b"ok"
                assert seen[0][1] is seen[1][1]
                assert seen[1][1] is not seen[2][1]
                assert all(
                    headers["Host"] == "origin.invalid" for _, _, headers in seen
                )
                assert all(
                    headers["Proxy-Authorization"].startswith("Basic ")
                    for _, _, headers in seen
                )
                assert all("Cookie" not in headers for _, _, headers in seen)
                await first.close()
                with pytest.raises(HTTPClientError, match="closed"):
                    await first.request("GET", "http://origin.invalid/ok")
                assert (
                    await peer.request("GET", "http://origin.invalid/ok")
                ).status_code == 200
            transport_logs = "\n".join(
                record.getMessage()
                for record in caplog.records
                if record.name.startswith(("httpx", "httpcore"))
            )
            for marker in (
                "synthetic-user",
                "synthetic-password",
                "synthetic-url-marker",
                "synthetic-access-marker",
            ):
                assert marker not in transport_logs
        finally:
            await first.close()
            await peer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,code,status",
    [
        ("denied", "status", 401),
        ("redirect", "status", 302),
        ("large", "response_too_large", None),
    ],
)
async def test_managed_proxy_requests_preserve_one_attempt_bounds_and_recover_capacity(
    path, code, status
):
    async with server() as (proxy, seen, _, _):
        client = ManagedHTTPClient(
            HTTPPolicy(
                max_connections=1, max_keepalive_connections=1, max_response_bytes=1024
            ),
            proxy=proxy,
        )
        try:
            with pytest.raises(HTTPClientError) as error:
                await client.request("GET", f"http://origin.invalid/{path}")
            assert error.value.code == code and error.value.status_code == status
            assert [entry[0] for entry in seen] == [f"/{path}"]
            assert (
                await client.request("GET", "http://origin.invalid/ok")
            ).body == b"ok"
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_proxy_connect_tls_failure_is_typed_and_does_not_log_destination(caplog):
    requests = []
    closed = asyncio.Event()

    async def proxy(reader, writer):
        try:
            requests.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            assert await reader.read(
                4096
            )  # Real TLS ClientHello, then injected disconnect.
        finally:
            writer.close()
            await writer.wait_closed()
            closed.set()

    listener = await asyncio.start_server(proxy, "127.0.0.1", 0)
    port = listener.sockets[0].getsockname()[1]
    client = ManagedHTTPClient(HTTPPolicy(), proxy=f"http://127.0.0.1:{port}")
    try:
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(HTTPClientError) as error:
                await client.request(
                    "GET", "https://synthetic-private-host.invalid/health"
                )
        assert error.value.code == "network"
        await asyncio.wait_for(closed.wait(), 5)
        assert len(requests) == 1
        assert requests[0].startswith(
            b"CONNECT synthetic-private-host.invalid:443 HTTP/1.1\r\n"
        )
        transport_logs = "\n".join(
            record.getMessage()
            for record in caplog.records
            if record.name.startswith(("httpx", "httpcore"))
        )
        assert "synthetic-private-host.invalid" not in transport_logs
    finally:
        await client.close()
        listener.close()
        await listener.wait_closed()
