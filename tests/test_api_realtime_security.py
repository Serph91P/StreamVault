from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast

from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketState

from app.middleware.auth import AuthMiddleware, _cookie_mutation_has_csrf_violation
from app.middleware_all import AdaptiveLimiter, rate_limit_middleware
from app.services.communication.websocket_manager import ConnectionManager
from app.utils.client_ip import get_client_info, get_real_client_ip


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeWebSocket:
    def __init__(
        self,
        *,
        peer: str = "198.51.100.1",
        headers: dict[str, str] | None = None,
        block_sends: bool = False,
    ) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.client = SimpleNamespace(host=peer)
        self.headers = headers or {"user-agent": "security-test"}
        self.messages: list[dict] = []
        self.close_codes: list[int] = []
        self.accepted = False
        self._send_gate = asyncio.Event()
        if not block_sends:
            self._send_gate.set()

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        await self._send_gate.wait()
        self.messages.append(message)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        del reason
        self.close_codes.append(code)
        self.client_state = WebSocketState.DISCONNECTED


def _request(peer: str, headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer, 1234),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def _mutation_request(
    *,
    origin: str | None = None,
    cookie: str | None = "access_token=session-token",
    authorization: str | None = None,
    api_key: str | None = None,
    fetch_site: str | None = None,
) -> Request:
    headers = [(b"host", b"streamvault.test")]
    for name, value in {
        "origin": origin,
        "cookie": cookie,
        "authorization": authorization,
        "x-api-key": api_key,
        "sec-fetch-site": fetch_site,
    }.items():
        if value is not None:
            headers.append((name.encode(), value.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/settings",
            "headers": headers,
            "client": ("198.51.100.1", 1234),
            "scheme": "https",
            "server": ("streamvault.test", 443),
        }
    )


def test_cookie_mutation_csrf_matrix_uses_selected_cookie_credentials():
    assert _cookie_mutation_has_csrf_violation(
        _mutation_request(origin="https://attacker.test")
    )
    assert not _cookie_mutation_has_csrf_violation(
        _mutation_request(origin="https://streamvault.test")
    )
    assert _cookie_mutation_has_csrf_violation(
        _mutation_request(origin=None, fetch_site="cross-site")
    )
    assert _cookie_mutation_has_csrf_violation(
        _mutation_request(
            origin="https://attacker.test", authorization="Bearer explicit-token"
        )
    )
    assert _cookie_mutation_has_csrf_violation(
        _mutation_request(origin="https://attacker.test", api_key="sv_explicit")
    )
    assert _cookie_mutation_has_csrf_violation(
        _mutation_request(
            origin="https://attacker.test", authorization="Basic irrelevant"
        )
    )
    assert not _cookie_mutation_has_csrf_violation(
        _mutation_request(origin="https://attacker.test", cookie=None)
    )
    assert not _cookie_mutation_has_csrf_violation(
        _mutation_request(
            origin="https://attacker.test",
            cookie=None,
            authorization="Bearer explicit-token",
        )
    )
    assert not _cookie_mutation_has_csrf_violation(
        _mutation_request(
            origin="https://attacker.test", cookie=None, api_key="sv_explicit"
        )
    )


def test_auth_middleware_blocks_cookie_csrf_with_irrelevant_authorization_header():
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/api/settings")
    async def mutate_settings():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post(
            "/api/settings",
            cookies={"access_token": "ambient-cookie"},
            headers={
                "Authorization": "Basic irrelevant",
                "Origin": "https://attacker.test",
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "CSRF validation failed"}


def test_http_and_websocket_forwarded_identity_have_trusted_proxy_parity(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
    trusted = _request("10.1.2.3", [(b"x-forwarded-for", b"203.0.113.9, 10.2.3.4")])
    spoofed = _request("198.51.100.4", [(b"x-forwarded-for", b"203.0.113.9")])

    assert get_real_client_ip(trusted) == "203.0.113.9"
    assert get_client_info(trusted)["is_reverse_proxied"] is True
    assert get_real_client_ip(spoofed) == "198.51.100.4"
    assert get_client_info(spoofed)["is_reverse_proxied"] is False


def test_rate_limit_middleware_validates_forwarded_identity_like_websocket(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])

    class CapturingLimiter:
        def __init__(self) -> None:
            self.client_ips: list[str] = []

        async def acquire(self, **kwargs):
            self.client_ips.append(kwargs["client_ip"])
            return True, 0, 99, 100

    def captured_ip(peer: str, forwarded_for: str) -> str:
        app = FastAPI()

        @app.get("/api/probe")
        async def probe():
            return {"ok": True}

        limiter = CapturingLimiter()
        app.state.rate_limiter = limiter
        app.middleware("http")(rate_limit_middleware)
        with TestClient(app, client=(peer, 50000)) as client:
            assert (
                client.get(
                    "/api/probe", headers={"X-Forwarded-For": forwarded_for}
                ).status_code
                == 200
            )
        return limiter.client_ips[-1]

    assert captured_ip("10.1.2.3", "203.0.113.9, 10.2.3.4") == "203.0.113.9"
    assert captured_ip("10.1.2.3", "not-an-ip") == "10.1.2.3"
    assert captured_ip("198.51.100.4", "203.0.113.9") == "198.51.100.4"


def test_rate_limiter_uses_monotonic_fake_clock_and_distinct_api_key_identities(
    monkeypatch,
):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_WAIT_MS", 0)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_BUCKETS", 2)
    clock = FakeClock()
    limiter = AdaptiveLimiter(clock=clock, sleep=clock.sleep)
    monkeypatch.setattr(limiter, "_route_params", lambda path, method: (1, 1.0))

    async def exercise():
        first = await limiter.acquire(
            path="/api/write",
            method="POST",
            client_ip="198.51.100.1",
            auth_header=None,
            api_key="key-one",
        )
        blocked = await limiter.acquire(
            path="/api/write",
            method="POST",
            client_ip="198.51.100.1",
            auth_header=None,
            api_key="key-one",
        )
        separate = await limiter.acquire(
            path="/api/write",
            method="POST",
            client_ip="198.51.100.1",
            auth_header="ApiKey key-two",
        )
        clock.now += 1.0
        refilled = await limiter.acquire(
            path="/api/write",
            method="POST",
            client_ip="198.51.100.1",
            auth_header=None,
            api_key="key-one",
        )
        return first, blocked, separate, refilled

    first, blocked, separate, refilled = asyncio.run(exercise())
    assert first[0] is True
    assert blocked[0] is False
    assert blocked[1] == 1
    assert separate[0] is True
    assert refilled[0] is True
    assert len(limiter._buckets) <= 2


def test_rate_limit_429_is_structured_json(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_WAIT_MS", 0)
    app = FastAPI()

    @app.post("/api/write")
    async def write():
        return {"ok": True}

    app.state.rate_limiter = AdaptiveLimiter()
    monkeypatch.setattr(
        app.state.rate_limiter, "_route_params", lambda path, method: (1, 0.01)
    )
    app.middleware("http")(rate_limit_middleware)

    with TestClient(app, client=("198.51.100.8", 50000)) as client:
        assert client.post("/api/write").status_code == 200
        response = client.post("/api/write")

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "error": {
            "code": "rate_limit_exceeded",
            "message": "Rate limit exceeded",
            "retry_after": int(response.headers["retry-after"]),
        }
    }


def test_slow_websocket_is_dropped_without_blocking_healthy_client():
    async def exercise():
        manager = ConnectionManager(event_log_size=5, queue_size=1)
        slow = FakeWebSocket(block_sends=True)
        healthy = FakeWebSocket(peer="198.51.100.2")
        manager.active_connections[id(slow)] = cast(WebSocket, slow)
        manager.active_connections[id(healthy)] = cast(WebSocket, healthy)
        manager._start_sender(cast(WebSocket, slow))
        manager._start_sender(cast(WebSocket, healthy))

        await manager.send_notification({"type": "one", "data": {}})
        await manager.send_notification({"type": "two", "data": {}})
        await manager.send_notification({"type": "three", "data": {}})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return manager, slow, healthy

    manager, slow, healthy = asyncio.run(exercise())
    assert id(slow) not in manager.active_connections
    assert slow.close_codes == [1013]
    assert [message["type"] for message in healthy.messages] == ["one", "two", "three"]


def test_connection_limits_and_concurrent_disconnect_are_bounded():
    async def exercise():
        manager = ConnectionManager(max_connections=1, max_connections_per_client=1)
        first = FakeWebSocket()
        second = FakeWebSocket(peer="198.51.100.2")
        assert await manager.connect(cast(WebSocket, first)) is True
        assert await manager.connect(cast(WebSocket, second)) is False
        await asyncio.gather(
            manager.disconnect(cast(WebSocket, first)),
            manager.disconnect(cast(WebSocket, first)),
        )
        return manager, second

    manager, rejected = asyncio.run(exercise())
    assert rejected.close_codes == [1013]
    assert manager.active_connections == {}


def test_concurrent_shutdown_closes_connections_and_awaits_sender_tasks():
    async def exercise():
        manager = ConnectionManager()
        first = FakeWebSocket()
        second = FakeWebSocket(peer="198.51.100.2")
        await manager.connect(cast(WebSocket, first))
        await manager.connect(cast(WebSocket, second))
        await manager.close_all()
        return manager, first, second

    manager, first, second = asyncio.run(exercise())
    assert manager.active_connections == {}
    assert manager._sender_tasks == {}
    assert first.close_codes == [1001]
    assert second.close_codes == [1001]


def test_replay_window_reports_gap_after_retention_overflow():
    async def exercise():
        manager = ConnectionManager(event_log_size=2)
        for event_type in ("one", "two", "three"):
            await manager.send_notification({"type": event_type, "data": {}})
        return await manager.get_replay_window(since=0, limit=10)

    window = asyncio.run(exercise())
    assert window["gap"] is True
    assert window["oldest_event_id"] == 2
    assert [event["event_id"] for event in window["events"]] == [2, 3]
