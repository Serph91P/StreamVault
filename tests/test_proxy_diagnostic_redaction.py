from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import ProxySettings
from app.routes import proxy as proxy_routes
from app.utils import proxy_encryption


PROXY_URL = (
    "https://route-user:route-password@proxy.example:8443/"
    "signed/path?token=route-secret#route-fragment"
)
SAFE_PROXY_URL = "proxy.example:8443"


class DeterministicEncryption:
    prefix = "encrypted::"

    def encrypt(self, plaintext):
        return f"{self.prefix}{plaintext}"

    def decrypt(self, encrypted):
        if not encrypted:
            return encrypted
        assert encrypted.startswith(self.prefix)
        return encrypted.removeprefix(self.prefix)


class FakeQuery:
    def __init__(self, model, proxy):
        self.model = model
        self.proxy = proxy

    def order_by(self, *args):
        return self

    def filter(self, *args):
        return self

    def all(self):
        return [self.proxy] if self.model is ProxySettings else []

    def first(self):
        return self.proxy if self.model is ProxySettings else None


class FakeDatabase:
    def __init__(self, proxy):
        self.proxy = proxy

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def query(self, model):
        return FakeQuery(model, self.proxy)


@pytest.fixture
def proxy_factory(monkeypatch):
    encryption = DeterministicEncryption()
    monkeypatch.setattr(proxy_encryption, "get_proxy_encryption", lambda: encryption)

    def make_proxy(url=PROXY_URL):
        proxy = ProxySettings()
        proxy.id = 1
        proxy.proxy_url = url
        proxy.priority = 0
        proxy.enabled = True
        proxy.health_status = "healthy"
        proxy.last_health_check = None
        proxy.average_response_time_ms = 25
        proxy.consecutive_failures = 0
        proxy.total_recordings = 4
        proxy.failed_recordings = 1
        proxy.created_at = None
        return proxy

    return make_proxy


def assert_safe_diagnostic_fields(payload, expected=SAFE_PROXY_URL):
    assert payload["proxy_url"] == expected
    assert payload["masked_url"] == expected


def test_default_serialization_redacts_every_non_host_component(proxy_factory):
    proxy = proxy_factory()

    assert proxy._proxy_url_encrypted != PROXY_URL
    assert proxy.proxy_url == PROXY_URL
    assert proxy.masked_url == SAFE_PROXY_URL
    assert_safe_diagnostic_fields(proxy.to_dict())
    assert proxy.to_dict(mask_password=False)["proxy_url"] == PROXY_URL
    assert proxy.to_dict(mask_password=False)["masked_url"] == SAFE_PROXY_URL


@pytest.mark.parametrize(
    ("proxy_url", "expected"),
    [
        ("", "[INVALID_URL]"),
        ("not-a-proxy-url/signed?token=secret", "[REDACTED_PROXY_URL]"),
    ],
)
def test_default_serialization_fails_closed(proxy_factory, proxy_url, expected):
    proxy = proxy_factory(proxy_url)

    assert proxy.masked_url == expected
    assert_safe_diagnostic_fields(proxy.to_dict(), expected)


def test_authenticated_list_and_best_routes_return_safe_diagnostics(
    monkeypatch, proxy_factory
):
    proxy = proxy_factory()
    monkeypatch.setattr(proxy_routes, "SessionLocal", lambda: FakeDatabase(proxy))

    async def get_best_proxy():
        return PROXY_URL

    monkeypatch.setattr(
        proxy_routes.proxy_health_service,
        "get_best_proxy",
        get_best_proxy,
    )

    app = FastAPI()
    app.include_router(proxy_routes.router)
    app.dependency_overrides[proxy_routes.get_current_user] = lambda: SimpleNamespace(
        id=1, is_admin=True
    )

    with TestClient(app) as client:
        list_response = client.get("/api/proxy/list")
        best_response = client.get("/api/proxy/best")

    assert list_response.status_code == 200
    assert best_response.status_code == 200
    assert_safe_diagnostic_fields(list_response.json()["proxies"][0])
    assert_safe_diagnostic_fields(best_response.json()["proxy"])
