"""Browser link transaction contract, with synthetic provider and storage boundaries."""

import time
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.bootstrap.application import create_app
from app.models import GlobalSettings
from app.services.api.twitch_oauth_service import TwitchOAuthService
from app.services.core.auth_service import AuthService
from app.services.system.twitch_token_service import TwitchTokenService
from tests import test_recording_capabilities as capabilities

stack = capabilities.stack


@pytest.fixture
def effects(stack, monkeypatch):
    _, database, _, _, _ = stack
    exchanges, stores = [], []
    pending, release = Event(), Event()

    async def exchange(self, code):
        exchanges.append(code)
        if code == "parallel-fixture":
            pending.set()
            assert release.wait(5)
        if code == "failed-fixture":
            return None
        return {
            "access_token": "synthetic-new-token",
            "refresh_token": "synthetic-new-refresh",
            "expires_in": 3600,
        }

    async def store(self, *, access_token, refresh_token, expires_in):
        stores.append(expires_in)
        with database.sync_session_factory() as db:
            row = db.get(GlobalSettings, 1)
            row.twitch_access_token = access_token
            row.twitch_refresh_token = refresh_token
            db.commit()
        return True

    monkeypatch.setattr(TwitchOAuthService, "exchange_code", exchange)
    monkeypatch.setattr(TwitchTokenService, "store_oauth_tokens", store)
    return exchanges, stores, pending, release


def stored(stack):
    with stack[1].sync_session_factory() as db:
        row = db.get(GlobalSettings, 1)
        return row.twitch_access_token, row.twitch_refresh_token


def begin(client, headers, destination="/settings"):
    response = client.get(
        "/api/twitch/auth-url", headers=headers, params={"state": destination}
    )
    assert response.status_code == 200
    return parse_qs(urlsplit(response.json()["auth_url"]).query)["state"][0]


def finish(client, headers, nonce, *, code: str | None = "link-fixture", **extra):
    params = dict(extra)
    if code is not None:
        params["code"] = code
    if nonce is not None:
        params["state"] = nonce
    return client.get(
        "/api/twitch/callback", headers=headers, params=params, follow_redirects=False
    )


@pytest.mark.parametrize(
    "mode,state,status",
    [
        ("jwt-cookie", "anonymous", 401),
        ("jwt-cookie", "reader", 403),
        ("jwt-bearer", "admin", 403),
        ("legacy-bearer", "admin", 403),
        ("key", "admin", 403),
        ("key-authorization", "admin", 403),
        ("legacy-cookie", "revoked", 401),
        ("jwt-cookie", "downgraded", 401),
    ],
)
def test_only_current_admin_browser_can_initiate(stack, effects, mode, state, status):
    response = stack[3].get(
        "/api/twitch/auth-url",
        headers=capabilities.headers(stack, mode, state),
        follow_redirects=False,
    )
    assert response.status_code == status
    assert effects[:2] == ([], [])
    assert stored(stack) == ("synthetic-old-token", "synthetic-old-refresh")


@pytest.mark.parametrize(
    "mode,dest,expected",
    [
        ("jwt-cookie", "/settings", "/settings"),
        ("legacy-cookie", "/add-streamer", "/add-streamer"),
        ("jwt-cookie", "https://untrusted.invalid/", "/settings"),
    ],
)
def test_session_links_once_with_safe_return(
    stack, effects, caplog, mode, dest, expected
):
    caplog.set_level("INFO", logger="streamvault")
    client = stack[3]
    browser = capabilities.headers(stack, mode, "admin")
    old = begin(client, browser, dest)
    nonce = begin(client, browser, dest)
    assert old != nonce and len(nonce) >= 32 and dest not in nonce
    assert (
        finish(client, browser, old).headers["location"]
        == "/add-streamer?error=auth_failed"
    )
    assert effects[:2] == ([], [])
    assert (
        finish(client, browser, nonce).headers["location"]
        == expected + "?auth_success=true"
    )
    assert (
        finish(client, browser, nonce).headers["location"]
        == "/add-streamer?error=auth_failed"
    )
    assert effects[:2] == (["link-fixture"], [3600])
    assert stored(stack) == ("synthetic-new-token", "synthetic-new-refresh")
    server_logs = [
        record.getMessage() for record in caplog.records if record.name == "streamvault"
    ]
    assert "Twitch OAuth link completed" in server_logs
    for value in (
        nonce,
        "link-fixture",
        "synthetic-new-token",
        "synthetic-new-refresh",
    ):
        assert all(value not in message for message in server_logs)


@pytest.mark.parametrize(
    "condition",
    [
        "missing",
        "wrong",
        "foreign-session",
        "no-cookie",
        "revoked",
        "downgraded",
        "expired",
        "restart",
        "cancel",
        "provider-failure",
    ],
)
def test_invalid_or_failed_flow_preserves_saved_credentials(
    stack, effects, monkeypatch, condition
):
    _, db, settings, client, _ = stack
    browser = capabilities.headers(stack, "legacy-cookie", "admin")
    nonce = begin(client, browser)
    callbacks = []
    if condition == "missing":
        nonce = None
    elif condition == "wrong":
        nonce = ("A" if nonce[0] != "A" else "B") + nonce[1:]
    elif condition in ("revoked", "downgraded", "foreign-session"):
        import asyncio

        token = browser["Cookie"].split("=", 1)[1]
        with db.sync_session_factory() as session:
            auth = AuthService(session, settings)
            user = auth.resolve_legacy_session(token)
            assert user is not None
            if condition == "revoked":
                auth.delete_session_sync(token)
            elif condition == "downgraded":
                user.is_admin = False
                session.commit()
            else:
                another = asyncio.run(auth.create_session(user.id))
                browser = {"Cookie": f"session={another}"}
    elif condition == "no-cookie":
        browser = {}
    elif condition == "expired":
        from app.services.api import twitch_oauth_service

        now = time.monotonic()
        monkeypatch.setattr(
            twitch_oauth_service, "monotonic", lambda: now + 900, raising=False
        )
    elif condition == "cancel":
        callbacks.append(
            finish(client, browser, nonce, code=None, error="access_denied")
        )
    elif condition == "provider-failure":
        callbacks.append(finish(client, browser, nonce, code="failed-fixture"))
    if condition == "restart":
        with_client = TestClient(create_app(settings=settings, database=db))
        try:
            callbacks.append(finish(with_client, browser, nonce))
        finally:
            with_client.close()
    else:
        callbacks.append(finish(client, browser, nonce))
    assert all(
        response.headers.get("location")
        in {"/settings?error=auth_failed", "/add-streamer?error=auth_failed"}
        for response in callbacks
    )
    assert effects[:2] == (
        ["failed-fixture"] if condition == "provider-failure" else [],
        [],
    )
    assert stored(stack) == ("synthetic-old-token", "synthetic-old-refresh")


@pytest.mark.parametrize("revoke_during_exchange", [False, True])
def test_concurrent_callback_is_consumed_before_exchange(
    stack, effects, revoke_during_exchange
):
    app, db, settings, client, _ = stack
    browser = capabilities.headers(stack, "legacy-cookie", "admin")
    nonce = begin(client, browser)
    _, _, pending, release = effects
    peer = TestClient(app)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(finish, client, browser, nonce, code="parallel-fixture")
            try:
                assert pending.wait(5)
                duplicate = pool.submit(finish, peer, browser, nonce)
                assert (
                    duplicate.result(timeout=5).headers["location"]
                    == "/add-streamer?error=auth_failed"
                )
                if revoke_during_exchange:
                    with db.sync_session_factory() as session:
                        AuthService(session, settings).delete_session_sync(
                            browser["Cookie"].split("=", 1)[1]
                        )
            finally:
                release.set()
            assert first.result(timeout=5).headers["location"] == (
                "/settings?error=auth_failed"
                if revoke_during_exchange
                else "/settings?auth_success=true"
            )
    finally:
        peer.close()
    assert effects[:2] == (
        ["parallel-fixture"],
        [] if revoke_during_exchange else [3600],
    )
    assert stored(stack) == (
        ("synthetic-old-token", "synthetic-old-refresh")
        if revoke_during_exchange
        else ("synthetic-new-token", "synthetic-new-refresh")
    )
