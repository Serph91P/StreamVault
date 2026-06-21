from datetime import datetime, timedelta
from types import SimpleNamespace

from app.routes.twitch_auth import _build_connection_status


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
