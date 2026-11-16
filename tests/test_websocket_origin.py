"""Real /ws handshakes with inert credential/DB seams, never real sessions."""

from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from app.config.settings import Settings
from app.middleware.auth import AuthMiddleware
from app.routes.realtime import router
from app.services.communication.websocket_manager import ConnectionManager


PUBLIC = "https://vault.example.test"
EXTRA = "https://dashboard.example.test:8443"


@pytest.fixture(params=["application-factory", "legacy-middleware"])
def handshake_stack(monkeypatch, request):
    import app.middleware.auth as auth
    import app.utils.client_ip as client_ip

    # model_validate avoids BaseSettings environment/.env sources entirely.
    settings = Settings.model_validate(
        {
            "TWITCH_APP_ID": "synthetic-app",
            "TWITCH_APP_SECRET": "synthetic-not-a-provider-credential",
            "BASE_URL": PUBLIC + "/installation",
            "CORS_ADDITIONAL_ORIGINS": EXTRA,
            "TRUSTED_PROXY_CIDRS": ["192.0.2.0/24"],
        }
    )
    monkeypatch.setattr(client_ip, "settings", settings)

    class InertSession:
        def close(self):
            pass

    class InertAuth:
        def __init__(self, db, settings=None):
            pass

        def resolve_access_token(self, token):
            if token == "synthetic-access":
                return SimpleNamespace()
            if token == "synthetic-unavailable":
                raise RuntimeError("synthetic service outage")
            raise ValueError("not a valid access credential")

        def resolve_legacy_session(self, token):
            if token == "synthetic-unavailable":
                raise RuntimeError("synthetic service outage")
            return SimpleNamespace() if token == "synthetic-legacy" else None

    monkeypatch.setattr(auth, "AuthService", InertAuth)
    database = SimpleNamespace(sync_session_factory=InertSession)
    if request.param == "application-factory":
        from app.main import create_app

        # Exercise the unchanged production composition without starting its
        # lifespan (which would bootstrap keys, databases and background jobs).
        app = create_app(settings=settings, database=database)
    else:
        app = FastAPI()
        app.state.settings = settings
        app.state.websocket_manager = ConnectionManager()
        app.include_router(router)
        monkeypatch.setattr(auth, "settings", settings)
        monkeypatch.setattr(auth, "SessionLocal", InertSession)
        app.add_middleware(AuthMiddleware)
    frames = []

    async def observed(scope, receive, send):
        async def capture(message):
            if scope["type"] == "websocket":
                frames.append(message)
            await send(message)

        await app(scope, receive, capture)

    return observed, frames, app.state.websocket_manager


CREDENTIALS = [
    pytest.param(
        {"cookie": "access_token=synthetic-access"}, True, 4001, id="access-cookie"
    ),
    pytest.param(
        {"cookie": "session=synthetic-legacy"}, True, 4001, id="legacy-cookie"
    ),
    pytest.param(
        {"authorization": "Bearer synthetic-access"}, True, 4001, id="access-bearer"
    ),
    pytest.param(
        {"authorization": "Bearer synthetic-legacy"}, True, 4001, id="legacy-bearer"
    ),
    pytest.param(
        {"cookie": "session=synthetic-invalid"}, False, 4001, id="invalid-cookie"
    ),
    pytest.param(
        {"authorization": "Bearer synthetic-invalid"}, False, 4001, id="invalid-bearer"
    ),
    pytest.param({}, False, 4001, id="missing-credentials"),
    pytest.param(
        {"cookie": "session=synthetic-unavailable"}, False, 4003, id="auth-error"
    ),
]
ORIGINS = [
    pytest.param([], True, id="nonbrowser-missing"),
    pytest.param([("origin", PUBLIC)], True, id="public-https"),
    pytest.param([("origin", EXTRA)], True, id="explicit-additional"),
    pytest.param(
        [("origin", "https://evil.example.test")], False, id="hostile-sibling"
    ),
    pytest.param([("origin", "https://attacker.test")], False, id="cross-site"),
    pytest.param([("origin", "null")], False, id="opaque-null"),
    pytest.param([("origin", "http://vault.example.test")], False, id="wrong-scheme"),
    pytest.param([("origin", PUBLIC + ":8443")], False, id="wrong-port"),
    pytest.param(
        [("origin", "http://internal.test:8080")],
        False,
        id="internal-host-not-authority",
    ),
    pytest.param([("origin", "")], False, id="empty-is-not-missing"),
    pytest.param([("origin", PUBLIC + "/")], False, id="path"),
    pytest.param([("origin", PUBLIC + "?query")], False, id="query"),
    pytest.param([("origin", " " + PUBLIC)], False, id="whitespace"),
    pytest.param(
        [("origin", PUBLIC + ", https://attacker.test")], False, id="comma-list"
    ),
    pytest.param(
        [("origin", PUBLIC + " https://attacker.test")], False, id="space-list"
    ),
    pytest.param(
        [("origin", PUBLIC), ("origin", "https://attacker.test")],
        False,
        id="duplicate-allowed-first",
    ),
    pytest.param(
        [("origin", "https://attacker.test"), ("origin", PUBLIC)],
        False,
        id="duplicate-allowed-last",
    ),
    pytest.param(
        [("origin", PUBLIC), ("origin", PUBLIC)], False, id="duplicate-identical"
    ),
]


@pytest.mark.parametrize("credential,valid,auth_close", CREDENTIALS)
@pytest.mark.parametrize("origin_headers,origin_allowed", ORIGINS)
def test_registered_handshake_checks_origin_before_every_accept(
    handshake_stack, credential, valid, auth_close, origin_headers, origin_allowed
):
    app, frames, manager = handshake_stack
    # An internal HTTP proxy target and spoofable browser/proxy headers cannot
    # authorize an Origin; the configured public HTTPS origin is authoritative.
    headers = httpx.Headers(
        [
            ("host", "internal.test:8080"),
            ("x-forwarded-host", "attacker.test"),
            ("x-forwarded-proto", "http"),
            ("sec-fetch-site", "same-origin"),
            *credential.items(),
            *origin_headers,
        ]
    )
    client = TestClient(app)
    try:
        if origin_allowed and valid:
            with client.websocket_connect(
                "ws://internal.test:8080/ws", headers=headers
            ) as ws:
                status = ws.receive_json()
                assert status["type"] == "connection.status"
                assert status["data"]["status"] == "connected"
                assert len(manager.active_connections) == 1
        else:
            with pytest.raises(WebSocketDisconnect) as rejected:
                with client.websocket_connect(
                    "ws://internal.test:8080/ws", headers=headers
                ) as ws:
                    ws.receive_json()
            assert rejected.value.code == (auth_close if origin_allowed else 1008)
    finally:
        client.close()

    if not origin_allowed:
        assert [frame["type"] for frame in frames] == ["websocket.close"]
    else:
        assert frames[0]["type"] == "websocket.accept"
    assert not manager.active_connections
    assert not manager._sender_tasks


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize(
    "cookie", ["access_token=synthetic-access", "session=synthetic-legacy"]
)
@pytest.mark.parametrize(
    "origin,expected",
    [
        (PUBLIC, 204),
        ("https://evil.example.test", 403),
        ("https://attacker.test", 403),
        (None, 204),
    ],
)
def test_http_cookie_csrf_controls_remain_unchanged(
    monkeypatch, method, cookie, origin, expected
):
    from fastapi import Response

    app = FastAPI()

    @app.api_route("/api/control", methods=["POST", "DELETE"])
    def control():
        return Response(status_code=204)

    # Isolate authentication, but run the original HTTP CSRF middleware branch.
    monkeypatch.setattr(
        AuthMiddleware, "_authorize_http", lambda *args: ("allow", None)
    )
    app.add_middleware(AuthMiddleware)
    headers = {"cookie": cookie}
    if origin is not None:
        headers["origin"] = origin
    with TestClient(app, base_url=PUBLIC) as client:
        response = client.request(method, "/api/control", headers=headers)
    assert response.status_code == expected
    if expected == 403:
        assert response.json() == {"error": "CSRF validation failed"}


def test_loopback_http_upgrade_accepts_public_origin_and_denies_sibling(
    handshake_stack,
):
    """Exercise real HTTP upgrade/403, not only TestClient ASGI semantics."""
    import json
    import socket
    from threading import Thread
    from time import monotonic, sleep

    import uvicorn
    from websockets.exceptions import InvalidStatus
    from websockets.sync.client import connect

    app, frames, manager = handshake_stack
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="error"))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]})
    thread.start()
    try:
        deadline = monotonic() + 5
        while not server.started and thread.is_alive() and monotonic() < deadline:
            sleep(0.01)
        assert server.started, "isolated loopback server did not start"
        url = f"ws://127.0.0.1:{listener.getsockname()[1]}/ws"
        headers = {"cookie": "session=synthetic-legacy"}
        with connect(url, origin=PUBLIC, additional_headers=headers, proxy=None) as ws:
            assert json.loads(ws.recv(timeout=3))["type"] == "connection.status"
        with pytest.raises(InvalidStatus) as rejected:
            connect(
                url,
                origin="https://evil.example.test",
                additional_headers=headers,
                proxy=None,
            )
        assert rejected.value.response.status_code == 403
        assert frames[-1]["type"] == "websocket.close"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive(), "isolated loopback server did not stop"
    assert not manager.active_connections
    assert not manager._sender_tasks
