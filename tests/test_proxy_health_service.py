import importlib
from types import SimpleNamespace

import pytest

from app.services.proxy.proxy_health_service import ProxyHealthService

proxy_health_module = importlib.import_module("app.services.proxy.proxy_health_service")


class _ProxyQuery:
    def __init__(self, proxies):
        self.proxies = proxies

    def filter(self, *_criteria):
        return self

    def all(self):
        return self.proxies


class _ProxySession:
    def __init__(self, proxies):
        self.proxies = proxies
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def query(self, _model):
        return _ProxyQuery(self.proxies)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        return None


def _proxy(proxy_id, proxy_url):
    return SimpleNamespace(
        id=proxy_id,
        proxy_url=proxy_url,
        masked_url=f"proxy-{proxy_id}",
        health_status="unknown",
        average_response_time_ms=None,
        consecutive_failures=0,
        enabled=True,
        last_health_check=None,
    )


@pytest.mark.asyncio
async def test_run_health_checks_reuses_one_unlogged_app_token_for_each_proxy(
    monkeypatch, caplog
):
    # Given: two enabled proxies and an in-memory app token
    proxies = [
        _proxy(1, "http://healthy-proxy.example:8080"),
        _proxy(2, "http://degraded-proxy.example:8080"),
        _proxy(3, "http://failed-proxy.example:8080"),
    ]
    session = _ProxySession(proxies)
    service = ProxyHealthService()
    token_fetches = []
    reachability_checks = []

    async def get_app_access_token():
        token_fetches.append(True)
        return "sensitive-app-token"

    async def check_proxy_health(proxy_url, access_token):
        reachability_checks.append((proxy_url, access_token))
        if "degraded" in proxy_url:
            return {
                "status": "degraded",
                "response_time_ms": 2200,
                "error": "Slow response (2200ms)",
            }
        if "failed" in proxy_url:
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Connection error",
            }
        return {
            "status": "healthy",
            "response_time_ms": 120,
            "error": None,
        }

    async def get_max_failures():
        return 3

    async def broadcast_proxy_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(proxy_health_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        service, "_get_app_access_token", get_app_access_token, raising=False
    )
    monkeypatch.setattr(service, "_check_proxy_health", check_proxy_health)
    monkeypatch.setattr(service, "_get_max_failures", get_max_failures)
    monkeypatch.setattr(service, "_broadcast_proxy_status", broadcast_proxy_status)

    # When: a complete proxy health cycle runs
    await service.run_health_checks()

    # Then: one token powers one API reachability request per proxy without log exposure.
    assert token_fetches == [True]
    assert reachability_checks == [
        ("http://healthy-proxy.example:8080", "sensitive-app-token"),
        ("http://degraded-proxy.example:8080", "sensitive-app-token"),
        ("http://failed-proxy.example:8080", "sensitive-app-token"),
    ]
    assert [proxy.health_status for proxy in proxies] == [
        "healthy",
        "degraded",
        "failed",
    ]
    assert [proxy.consecutive_failures for proxy in proxies] == [0, 0, 1]
    assert session.commit_count == 3
    assert "sensitive-app-token" not in caplog.text


@pytest.mark.asyncio
async def test_run_health_checks_marks_each_proxy_failed_when_token_fetch_fails(
    monkeypatch,
):
    # Given: enabled proxies and a failed app-token request
    proxies = [
        _proxy(1, "http://first-proxy.example:8080"),
        _proxy(2, "http://second-proxy.example:8080"),
    ]
    session = _ProxySession(proxies)
    service = ProxyHealthService()

    async def get_app_access_token():
        return None

    async def get_max_failures():
        return 3

    async def broadcast_proxy_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(proxy_health_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(service, "_get_app_access_token", get_app_access_token)
    monkeypatch.setattr(service, "_get_max_failures", get_max_failures)
    monkeypatch.setattr(service, "_broadcast_proxy_status", broadcast_proxy_status)

    # When: the health-check cycle cannot obtain its app token
    await service.run_health_checks()

    # Then: no unauthenticated reachability call is made and failures are recorded.
    assert [proxy.health_status for proxy in proxies] == ["failed", "failed"]
    assert [proxy.consecutive_failures for proxy in proxies] == [1, 1]


@pytest.mark.asyncio
async def test_run_health_checks_propagates_cancellation(monkeypatch):
    # Given: a health check blocked on its one proxy request
    import asyncio

    proxy = _proxy(1, "http://blocked-proxy.example:8080")
    session = _ProxySession([proxy])
    service = ProxyHealthService()
    request_started = asyncio.Event()
    never_finishes = asyncio.Event()

    async def get_app_access_token():
        return "sensitive-app-token"

    async def check_proxy_health(_proxy_url, _access_token):
        request_started.set()
        await never_finishes.wait()

    monkeypatch.setattr(proxy_health_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(service, "_get_app_access_token", get_app_access_token)
    monkeypatch.setattr(service, "_check_proxy_health", check_proxy_health)

    # When: the caller cancels the active health-check cycle
    task = asyncio.create_task(service.run_health_checks())
    await request_started.wait()
    task.cancel()

    # Then: cancellation is not converted into a proxy failure.
    with pytest.raises(asyncio.CancelledError):
        await task
    assert proxy.health_status == "unknown"
