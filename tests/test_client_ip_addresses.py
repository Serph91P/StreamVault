"""#944: real proxy extraction must not collapse IPv6 clients into one bucket."""

import pytest
from starlette.requests import Request
from starlette.websockets import WebSocket

from app.config.settings import Settings
from app.utils import client_ip


@pytest.mark.parametrize(
    "address",
    [
        "203.0.113.42",
        "203.0.113.42:443",
        "2001:db8::42",
        "2001:db8:85a3:0:0:8a2e:370:7334",
        "[2001:db8::42]:443",
        "[2001:db8::42]",
        "::ffff:203.0.113.42",
    ],
)
def test_valid_forwarded_addresses(address):
    assert client_ip.is_valid_ip(address)


@pytest.mark.parametrize(
    "address",
    [
        "",
        "unknown",
        "localhost",
        "127.0.0.1",
        "::1",
        "[::1]:443",
        "203.0.113.42:bad",
        "203.0.113.42:0",
        "203.0.113.42:65536",
        "203.0.113.042",
        "256.0.0.1",
        "2001::db8::42",
        "1:2:3",
        "[2001:db8::42]:bad",
        "[2001:db8::42]:-1",
        "[2001:db8::42]junk",
        "2001:db8::42%eth0",
        "203.0.113.42, 203.0.113.43",
        pytest.param("203.0.113.42:" + "9" * 5000, id="ipv4-oversized-port"),
        pytest.param("[2001:db8::42]:" + "9" * 5000, id="ipv6-oversized-port"),
    ],
)
def test_invalid_forwarded_addresses(address):
    assert not client_ip.is_valid_ip(address)


def connection(kind, peer, header, value):
    scope = {
        "type": kind,
        "scheme": "http" if kind == "http" else "ws",
        "path": "/api/status",
        "query_string": b"",
        "server": ("testserver", 80),
        "client": (peer, 12345),
        "headers": [(header.encode(), value.encode())],
    }

    async def receive():
        return {"type": "websocket.disconnect"}

    async def send(message):
        pass

    return Request(scope) if kind == "http" else WebSocket(scope, receive, send)


@pytest.fixture
def trusted_proxy(monkeypatch):
    configuration = Settings(
        _env_file=None,
        TWITCH_APP_ID="synthetic",
        TWITCH_APP_SECRET="synthetic",
        BASE_URL="https://example.test",
        TRUSTED_PROXY_CIDRS=["192.0.2.0/24"],
    )
    monkeypatch.setattr(client_ip, "settings", configuration)


@pytest.mark.parametrize("kind", ["http", "websocket"])
@pytest.mark.parametrize(
    ("header", "value", "expected"),
    [
        ("x-forwarded-for", "2001:db8::42, 192.0.2.2", "2001:db8::42"),
        ("x-real-ip", "2001:0db8:0:0:0:0:0:42", "2001:db8::42"),
        ("forwarded", 'for="[2001:db8::42]:443";proto=https', "2001:db8::42"),
        ("x-real-ip", "203.0.113.42:443", "203.0.113.42"),
        ("x-real-ip", "2001::db8::42", "192.0.2.1"),
        pytest.param(
            "x-real-ip",
            "203.0.113.42:" + "9" * 5000,
            "192.0.2.1",
            id="ipv4-oversized-port",
        ),
        pytest.param(
            "x-real-ip",
            "[2001:db8::42]:" + "9" * 5000,
            "192.0.2.1",
            id="ipv6-oversized-port",
        ),
    ],
)
def test_actual_http_and_websocket_extraction(
    trusted_proxy, kind, header, value, expected
):
    assert (
        client_ip.get_real_client_ip(connection(kind, "192.0.2.1", header, value))
        == expected
    )
    assert (
        client_ip.get_real_client_ip(connection(kind, "198.51.100.1", header, value))
        == "198.51.100.1"
    )


@pytest.mark.asyncio
async def test_distinct_ipv6_clients_keep_independent_rate_buckets(trusted_proxy):
    from app.middleware_all import AdaptiveLimiter

    limiter = AdaptiveLimiter()
    first = client_ip.get_real_client_ip(
        connection("http", "192.0.2.1", "x-real-ip", "2001:db8::42")
    )
    second = client_ip.get_real_client_ip(
        connection("http", "192.0.2.1", "x-real-ip", "2001:db8::43")
    )
    assert first == "2001:db8::42"
    assert second == "2001:db8::43"
    await limiter.acquire(
        path="/api/status",
        method="GET",
        client_ip=first,
        auth_header=None,
        api_key=None,
    )
    await limiter.acquire(
        path="/api/status",
        method="GET",
        client_ip=second,
        auth_header=None,
        api_key=None,
    )
    assert len(limiter._buckets) == 2
