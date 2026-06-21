import importlib.util
from pathlib import Path

import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace

_module_path = (
    Path(__file__).resolve().parents[1]
    / "app/services/system/twitch_token_service.py"
)
_spec = importlib.util.spec_from_file_location(
    "twitch_token_service_under_test", _module_path
)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
TwitchTokenService = _module.TwitchTokenService


class _Query:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Db:
    def __init__(self, settings):
        self.settings = settings
        self.committed = False
        self.rolled_back = False

    def query(self, _model):
        return _Query(self.settings)

    def refresh(self, _obj):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _Encryption:
    def encrypt(self, value):
        return f"enc:{value}"

    def decrypt(self, value):
        return value.removeprefix("enc:")


@pytest.mark.asyncio
async def test_manual_database_token_preferred_over_environment_token(monkeypatch):
    stored = SimpleNamespace(
        twitch_access_token="enc:db-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    service = TwitchTokenService.__new__(TwitchTokenService)
    service.db = _Db(stored)
    service.settings = SimpleNamespace(TWITCH_OAUTH_TOKEN="env-token")
    service.encryption = _Encryption()

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_send_expiry_notification_if_needed", _noop)

    assert await service.get_valid_access_token() == "db-token"


@pytest.mark.asyncio
async def test_environment_token_used_as_fallback_when_database_token_expired(monkeypatch):
    stored = SimpleNamespace(
        twitch_access_token="enc:expired-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    service = TwitchTokenService.__new__(TwitchTokenService)
    service.db = _Db(stored)
    service.settings = SimpleNamespace(TWITCH_OAUTH_TOKEN="env-token")
    service.encryption = _Encryption()

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_send_expiry_notification_if_needed", _noop)

    assert await service.get_valid_access_token() == "env-token"


@pytest.mark.asyncio
async def test_environment_token_preferred_over_refreshable_oauth_token(monkeypatch):
    stored = SimpleNamespace(
        twitch_access_token="enc:app-oauth-token",
        twitch_refresh_token="enc:refresh-token",
        twitch_token_expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    service = TwitchTokenService.__new__(TwitchTokenService)
    service.db = _Db(stored)
    service.settings = SimpleNamespace(TWITCH_OAUTH_TOKEN="env-browser-token")
    service.encryption = _Encryption()

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_send_expiry_notification_if_needed", _noop)

    assert await service.get_valid_access_token() == "env-browser-token"


@pytest.mark.asyncio
async def test_store_manual_access_token_encrypts_and_clears_refresh_token(monkeypatch):
    stored = SimpleNamespace(
        twitch_access_token=None,
        twitch_refresh_token="enc:old-refresh",
        twitch_token_expires_at=None,
    )
    service = TwitchTokenService.__new__(TwitchTokenService)
    service.db = _Db(stored)
    service.settings = SimpleNamespace(TWITCH_OAUTH_TOKEN=None)
    service.encryption = _Encryption()

    async def _validate(token):
        assert token == "manual-token"
        return {"expires_in": 3600}

    monkeypatch.setattr(service, "validate_token", _validate)

    success, validation = await service.store_manual_access_token("OAuth manual-token")

    assert success is True
    assert validation == {"expires_in": 3600}
    assert stored.twitch_access_token == "enc:manual-token"
    assert stored.twitch_refresh_token is None
    assert stored.twitch_token_expires_at is not None
    assert service.db.committed is True
