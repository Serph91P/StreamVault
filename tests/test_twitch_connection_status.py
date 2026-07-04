from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.routes.twitch_auth import _build_connection_status, get_connection_status


def test_connection_status_uses_env_when_manual_database_token_is_expired():
    stored = SimpleNamespace(
        twitch_access_token="encrypted-old-browser-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=datetime.utcnow() - timedelta(minutes=5),
    )

    status = _build_connection_status(stored, "env-browser-token")

    assert status == {
        "connected": True,
        "valid": True,
        "expires_at": None,
        "source": "environment",
        "has_env_token": True,
    }


def test_connection_status_reports_fresh_manual_database_token():
    expires_at = datetime.utcnow() + timedelta(days=30)
    stored = SimpleNamespace(
        twitch_access_token="encrypted-new-browser-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=expires_at,
    )

    status = _build_connection_status(stored, "env-browser-token")

    assert status["connected"] is True
    assert status["valid"] is True
    assert status["expires_at"] == expires_at.isoformat()
    assert status["source"] == "database_manual"
    assert status["has_env_token"] is True


def test_connection_status_keeps_expired_manual_database_status_without_env_fallback():
    expires_at = datetime.utcnow() - timedelta(days=1)
    stored = SimpleNamespace(
        twitch_access_token="encrypted-old-browser-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=expires_at,
    )

    status = _build_connection_status(stored, None)

    assert status["connected"] is True
    assert status["valid"] is False
    assert status["expires_at"] == expires_at.isoformat()
    assert status["source"] == "database_manual"
    assert status["has_env_token"] is False


class _Query:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Db:
    def __init__(self, settings):
        self.settings = settings

    def query(self, _model):
        return _Query(self.settings)


class _SessionContext:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *_args):
        return False


async def _fake_revalidate(_service, global_settings):
    global_settings.twitch_token_expires_at = datetime.utcnow() + timedelta(days=30)
    return True


async def _fake_failed_revalidate(_service, _global_settings):
    return False


async def _call_connection_status(monkeypatch, stored, env_token, revalidate):
    import app.config.settings as settings_module
    import app.database as database_module
    from app.services.system.twitch_token_service import TwitchTokenService

    monkeypatch.setattr(settings_module.settings, "TWITCH_OAUTH_TOKEN", env_token)
    monkeypatch.setattr(
        database_module, "SessionLocal", lambda: _SessionContext(_Db(stored))
    )
    monkeypatch.setattr(
        TwitchTokenService, "revalidate_stored_manual_token", revalidate
    )

    return await get_connection_status()


@pytest.mark.asyncio
async def test_connection_status_repairs_valid_stale_manual_token_before_env_fallback(
    monkeypatch,
):
    stored = SimpleNamespace(
        twitch_access_token="encrypted-new-browser-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=datetime.utcnow() - timedelta(days=1),
    )

    status = await _call_connection_status(
        monkeypatch, stored, "env-browser-token", _fake_revalidate
    )

    assert status["connected"] is True
    assert status["valid"] is True
    assert status["source"] == "database_manual"
    assert status["has_env_token"] is True
    assert status["expires_at"] == stored.twitch_token_expires_at.isoformat()


@pytest.mark.asyncio
async def test_connection_status_reports_env_when_stale_manual_token_revalidation_fails(
    monkeypatch,
):
    stored = SimpleNamespace(
        twitch_access_token="encrypted-old-browser-token",
        twitch_refresh_token=None,
        twitch_token_expires_at=datetime.utcnow() - timedelta(days=1),
    )

    status = await _call_connection_status(
        monkeypatch, stored, "env-browser-token", _fake_failed_revalidate
    )

    assert status == {
        "connected": True,
        "valid": True,
        "expires_at": None,
        "source": "environment",
        "has_env_token": True,
    }
