"""Real callback/router/token-store flow against synthetic loopback grants."""

import asyncio
from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app.dependencies import (
    get_application_twitch_oauth_service,
    get_application_twitch_token_service,
)
from app.lifespan import _close_application_twitch
from app.services.api.twitch_oauth_service import TwitchOAuthService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_proxy_http_ownership, test_oauth_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
async def test_callback_exchanges_once_and_persists_only_its_owner(
    proxy_applications, monkeypatch, caplog
):
    applications, databases, clients, queries = proxy_applications
    payload = {
        "access_token": "fixture-callback-access",
        "refresh_token": "fixture-callback-refresh",
        "expires_in": 7200,
    }
    async with test_oauth_http_ownership.oauth_origin(payload) as (
        _,
        _,
        transports,
        seen,
    ):
        try:
            for index, app in enumerate(applications):
                app.state.settings.TWITCH_APP_ID = f"fixture-id-{index}"
                from pydantic import SecretStr

                app.state.settings.twitch_app_secret = SecretStr(
                    f"fixture-secret-{index}"
                )
                app.state.settings.BASE_URL = f"https://owner-{index}.invalid"
                connection = HTTPConnection({"type": "http", "app": app, "headers": []})
                actor = await run_in_thread_pool(
                    get_application_twitch_oauth_service, connection
                )
                request = transports[index].request

                async def local(method, url, *, _request=request, **kwargs):
                    assert all(
                        db.sync_engine.pool.checkedout() == 0 for db in databases
                    )
                    return await _request(method, url, **kwargs)

                monkeypatch.setattr(actor._http, "request", local)
                queries.clear()
                callback = await clients[index].get(
                    "/api/twitch/callback",
                    params={
                        "code": "fixture-code",
                        "state": "/add-streamer"
                        if index == 0
                        else "https://foreign.invalid",
                    },
                )
                assert callback.status_code == 307
                assert callback.headers["location"] == (
                    "/add-streamer?auth_success=true"
                    if index == 0
                    else "/settings?auth_success=true"
                )
                stored = get_application_twitch_token_service(connection)
                state = await stored.get_state()
                assert state is not None
                assert state.twitch_access_token != payload["access_token"]
                assert state.twitch_refresh_token != payload["refresh_token"]

                def decrypted():
                    from app.utils.proxy_encryption import get_proxy_encryption

                    with databases[index].sync_session_factory() as session:
                        cipher = get_proxy_encryption(session)
                        return (
                            cipher.decrypt(state.twitch_access_token),
                            cipher.decrypt(state.twitch_refresh_token),
                        )

                assert await run_in_thread_pool(decrypted) == (
                    payload["access_token"],
                    payload["refresh_token"],
                )
                assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
                writes = [
                    thread for thread, sql in queries if "UPDATE global_settings" in sql
                ]
                assert writes and get_ident() not in writes
                if index == 0:
                    peer = get_application_twitch_token_service(
                        HTTPConnection(
                            {"type": "http", "app": applications[1], "headers": []}
                        )
                    )
                    assert (await peer.get_state()).twitch_access_token is None
            assert len(seen) == 2
            assert [form["client_id"] for _, form, _ in seen] == [
                "fixture-id-0",
                "fixture-id-1",
            ]
            assert "fixture-callback-access" not in caplog.text
            assert "fixture-callback-refresh" not in caplog.text
        finally:
            for app in applications:
                await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_owned_oauth_transport_close_drains_repeated_cancellation(monkeypatch):
    actor = TwitchOAuthService()
    entered, release = asyncio.Event(), asyncio.Event()
    native = actor._http.close

    async def close():
        entered.set()
        await release.wait()
        await native()

    monkeypatch.setattr(actor._http, "close", close)
    closing = asyncio.create_task(actor.close())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()
        assert not actor._http._closed
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await closing
        assert actor._http._closed
        assert actor._close_task.done()
        await actor.close()
    finally:
        release.set()
        await asyncio.gather(closing, return_exceptions=True)
        await actor.close()
