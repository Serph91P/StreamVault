import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

import pytest


class FakeResponse:
    def __init__(self, status, payload=None, body=""):
        self.status = status
        self.payload = payload or {}
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return self.body


class RaisingRequest:
    def __init__(self, error):
        self.error = error

    async def __aenter__(self):
        raise self.error

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class RecordingSession:
    def __init__(self, recorder, responses, **kwargs):
        self.recorder = recorder
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, **kwargs):
        self.recorder["token_requests"] += 1
        return self.responses["token"]

    def get(self, url, **kwargs):
        self.recorder["reachability_requests"] += 1
        self.recorder["authorization_values"].append(kwargs["headers"]["Authorization"])
        self.recorder["redirect_values"].append(kwargs["allow_redirects"])
        return self.responses["proxies"].pop(0)


class FakeQuery:
    def __init__(self, proxies):
        self.proxies = proxies

    def filter(self, *args):
        return self

    def all(self):
        return self.proxies


class FakeDatabase:
    def __init__(self, proxies):
        self.proxies = proxies

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def query(self, model):
        return FakeQuery(self.proxies)

    def commit(self):
        pass

    def rollback(self):
        pass


def make_proxy(proxy_id, url):
    return SimpleNamespace(
        id=proxy_id,
        proxy_url=url,
        masked_url=url,
        enabled=True,
        consecutive_failures=0,
        health_status="unknown",
        average_response_time_ms=None,
    )


@pytest.fixture
def proxy_health_module(monkeypatch):
    constants_module = ModuleType("app.config.constants")
    constants_module.ASYNC_DELAYS = SimpleNamespace(PROXY_HEALTH_CHECK_ERROR_WAIT=1)
    settings_module = ModuleType("app.config.settings")
    settings_module.settings = SimpleNamespace(
        TWITCH_APP_ID="test-app-id",
        TWITCH_APP_SECRET="test-app-secret",
    )
    database_module = ModuleType("app.database")
    database_module.SessionLocal = lambda: None
    models_module = ModuleType("app.models")

    class EnabledField:
        def is_(self, value):
            return value

    models_module.ProxySettings = type("ProxySettings", (), {"enabled": EnabledField()})
    models_module.RecordingSettings = type("RecordingSettings", (), {})

    monkeypatch.setitem(sys.modules, "app.config.constants", constants_module)
    monkeypatch.setitem(sys.modules, "app.config.settings", settings_module)
    monkeypatch.setitem(sys.modules, "app.database", database_module)
    monkeypatch.setitem(sys.modules, "app.models", models_module)

    module_path = (
        Path(__file__).parents[1]
        / "app"
        / "services"
        / "proxy"
        / "proxy_health_service.py"
    )
    spec = importlib.util.spec_from_file_location(
        "proxy_health_service_under_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_fakes(monkeypatch, proxy_health_module, proxies, responses):
    recorder = {
        "token_requests": 0,
        "reachability_requests": 0,
        "authorization_values": [],
        "redirect_values": [],
    }
    monkeypatch.setattr(
        proxy_health_module,
        "SessionLocal",
        lambda: FakeDatabase(proxies),
    )
    monkeypatch.setattr(
        proxy_health_module.aiohttp,
        "ClientSession",
        lambda **kwargs: RecordingSession(recorder, responses, **kwargs),
    )
    monkeypatch.setattr(proxy_health_module.aiohttp, "TCPConnector", lambda: object())
    return recorder


async def prepare_service(monkeypatch, proxy_health_module):
    service = proxy_health_module.ProxyHealthService()

    async def max_failures():
        return 3

    async def broadcast(proxy, auto_disabled=False):
        pass

    monkeypatch.setattr(service, "_get_max_failures", max_failures)
    monkeypatch.setattr(service, "_broadcast_proxy_status", broadcast)
    return service


@pytest.mark.asyncio
async def test_cycle_uses_one_token_and_one_request_per_proxy(
    monkeypatch, proxy_health_module
):
    token = "cycle-token-secret"
    proxies = [
        make_proxy(1, "http://first.example:8080"),
        make_proxy(2, "https://second.example:8443"),
    ]
    responses = {
        "token": FakeResponse(200, {"access_token": token}),
        "proxies": [FakeResponse(200), FakeResponse(302)],
    }
    recorder = install_fakes(monkeypatch, proxy_health_module, proxies, responses)
    service = await prepare_service(monkeypatch, proxy_health_module)

    await service.run_health_checks()

    assert recorder["token_requests"] == 1
    assert recorder["reachability_requests"] == len(proxies)
    assert len(recorder["authorization_values"]) == len(proxies)
    assert all(value == f"Bearer {token}" for value in recorder["authorization_values"])
    assert recorder["redirect_values"] == [False, False]
    assert [proxy.health_status for proxy in proxies] == ["healthy", "healthy"]


@pytest.mark.asyncio
async def test_token_failure_stops_before_reachability_request(
    monkeypatch, caplog, proxy_health_module
):
    response_secret = "token-response-body-secret"
    proxies = [make_proxy(1, "http://proxy.example:8080")]
    responses = {
        "token": FakeResponse(503, body=response_secret),
        "proxies": [FakeResponse(200)],
    }
    recorder = install_fakes(monkeypatch, proxy_health_module, proxies, responses)
    service = await prepare_service(monkeypatch, proxy_health_module)

    with caplog.at_level(logging.ERROR, logger="streamvault"):
        await service.run_health_checks()

    assert recorder["token_requests"] == 1
    assert recorder["reachability_requests"] == 0
    assert response_secret not in caplog.text


@pytest.mark.asyncio
async def test_proxy_failure_is_isolated_without_secret_leaks(
    monkeypatch, caplog, proxy_health_module
):
    token = "isolated-token-secret"
    exception_secret = "signed.example/path?signature=exception-secret#fragment-secret"
    proxy_secret = "proxy-user-secret"
    proxies = [
        make_proxy(
            1,
            f"http://{proxy_secret}:password-secret@first.example:8080/path?key=query-secret#fragment-secret",
        ),
        make_proxy(2, "http://second.example:8080"),
    ]
    responses = {
        "token": FakeResponse(200, {"access_token": token}),
        "proxies": [
            RaisingRequest(RuntimeError(exception_secret)),
            FakeResponse(401, body="response-body-secret"),
        ],
    }
    recorder = install_fakes(monkeypatch, proxy_health_module, proxies, responses)
    service = await prepare_service(monkeypatch, proxy_health_module)

    with caplog.at_level(logging.INFO, logger="streamvault"):
        await service.run_health_checks()

    assert recorder["token_requests"] == 1
    assert recorder["reachability_requests"] == len(proxies)
    assert [proxy.health_status for proxy in proxies] == [
        "failed",
        "degraded",
    ]
    for secret in (
        token,
        exception_secret,
        proxy_secret,
        "password-secret",
        "query-secret",
        "fragment-secret",
        "response-body-secret",
    ):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_proxy_request_cancellation_propagates_and_stops_cycle(
    monkeypatch, caplog, proxy_health_module
):
    cancellation_secret = "proxy-cancel-secret"
    token = "cancellation-token-secret"
    proxies = [
        make_proxy(1, "http://first.example:8080"),
        make_proxy(2, "http://second.example:8080"),
        make_proxy(3, "http://third.example:8080"),
    ]
    responses = {
        "token": FakeResponse(200, {"access_token": token}),
        "proxies": [
            FakeResponse(200),
            RaisingRequest(asyncio.CancelledError(cancellation_secret)),
            FakeResponse(200),
        ],
    }
    recorder = install_fakes(monkeypatch, proxy_health_module, proxies, responses)
    service = await prepare_service(monkeypatch, proxy_health_module)

    with caplog.at_level(logging.INFO, logger="streamvault"):
        with pytest.raises(asyncio.CancelledError):
            await service.run_health_checks()

    assert recorder["token_requests"] == 1
    assert recorder["reachability_requests"] == 2
    assert [proxy.health_status for proxy in proxies] == [
        "healthy",
        "unknown",
        "unknown",
    ]
    assert cancellation_secret not in caplog.text
    assert token not in caplog.text


@pytest.mark.asyncio
async def test_token_request_cancellation_propagates_without_reachability(
    monkeypatch, caplog, proxy_health_module
):
    cancellation_secret = "token-cancel-secret"
    proxies = [make_proxy(1, "http://proxy.example:8080")]
    responses = {
        "token": RaisingRequest(asyncio.CancelledError(cancellation_secret)),
        "proxies": [FakeResponse(200)],
    }
    recorder = install_fakes(monkeypatch, proxy_health_module, proxies, responses)
    service = await prepare_service(monkeypatch, proxy_health_module)

    with caplog.at_level(logging.ERROR, logger="streamvault"):
        with pytest.raises(asyncio.CancelledError):
            await service.run_health_checks()

    assert recorder["token_requests"] == 1
    assert recorder["reachability_requests"] == 0
    assert cancellation_secret not in caplog.text


@pytest.mark.asyncio
async def test_token_exception_returns_generic_diagnostic(
    monkeypatch, caplog, proxy_health_module
):
    exception_secret = "oauth-exception-secret"
    responses = {
        "token": RaisingRequest(RuntimeError(exception_secret)),
        "proxies": [],
    }
    recorder = install_fakes(monkeypatch, proxy_health_module, [], responses)
    service = await prepare_service(monkeypatch, proxy_health_module)

    with caplog.at_level(logging.ERROR, logger="streamvault"):
        result = await service._get_twitch_access_token()

    assert result is None
    assert recorder["token_requests"] == 1
    assert exception_secret not in caplog.text


@pytest.mark.asyncio
async def test_broadcast_diagnostic_and_repr_retain_only_proxy_host_port(
    monkeypatch, proxy_health_module
):
    messages = []

    class WebsocketManager:
        async def send_notification(self, message):
            messages.append(message)

    websocket_module = ModuleType("app.services.communication.websocket_manager")
    websocket_module.websocket_manager = WebsocketManager()
    monkeypatch.setitem(sys.modules, "app.services", ModuleType("app.services"))
    monkeypatch.setitem(
        sys.modules,
        "app.services.communication",
        ModuleType("app.services.communication"),
    )
    monkeypatch.setitem(
        sys.modules, "app.services.communication.websocket_manager", websocket_module
    )

    proxy_url = (
        "http://broadcast-user:broadcast-password@proxy.example:8080/"
        "signed/path?token=broadcast-query#broadcast-fragment"
    )
    proxy = SimpleNamespace(
        proxy_url=proxy_url,
        to_dict=lambda mask_password=True: {
            "proxy_url": proxy_url,
            "masked_url": proxy_url,
        },
    )
    service = proxy_health_module.ProxyHealthService()

    await service._broadcast_proxy_status(proxy)

    assert messages[0]["proxy"]["proxy_url"] == "proxy.example:8080"
    assert messages[0]["proxy"]["masked_url"] == "proxy.example:8080"
    diagnostic_repr = repr(messages)
    for secret in (
        "broadcast-user",
        "broadcast-password",
        "signed",
        "broadcast-query",
        "broadcast-fragment",
    ):
        assert secret not in diagnostic_repr
