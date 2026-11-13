"""Twitch HTTP status/failure contracts use the actual owner token catalogue."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import (
    _close_application_twitch,
    _close_application_proxy,
    _close_application_logging,
)
from app.models import GlobalSettings
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_proxy_http_ownership import proxy_applications as proxy_applications
from tests.test_proxy_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["oauth-valid", "oauth-expired", "refresh-only"])
async def test_owned_oauth_connection_status_never_claims_expired_access_valid(
    proxy_applications, kind
):
    apps, databases, clients, _ = proxy_applications
    app, database = apps[0], databases[0]
    app.state.settings.TWITCH_OAUTH_TOKEN = None
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app}),
    )
    try:
        assert await service.store_oauth_tokens(
            "fixture-status", "fixture-refresh", 7200
        )
        if kind != "oauth-valid":
            with database.sync_session_factory() as session:
                row = session.query(GlobalSettings).one()
                row.twitch_token_expires_at = datetime.now(timezone.utc).replace(
                    tzinfo=None
                ) - timedelta(minutes=1)
                if kind == "refresh-only":
                    row.twitch_access_token = None
                session.commit()
        response = await clients[0].get("/api/twitch/connection-status")
        assert response.status_code == 200
        body = response.json()
        assert body["connected"] is True and body["valid"] is (kind == "oauth-valid")
        assert body["source"] == (
            "oauth_refresh" if kind == "refresh-only" else "database_oauth"
        )
        assert body["has_env_token"] is False
        assert (
            "fixture-status" not in response.text
            and "fixture-refresh" not in response.text
        )
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["connection-status", "disconnect"])
async def test_twitch_catalogue_failure_does_not_claim_connected_or_disconnected(
    proxy_applications, path
):
    apps, databases, clients, _ = proxy_applications
    database = databases[0]
    app = apps[0]
    app.state.settings.TWITCH_OAUTH_TOKEN = None
    seen = []

    def unavailable(_connection, _cursor, statement, *_args):
        if "global_settings" in statement:
            seen.append(statement)
            raise OSError("synthetic-twitch-catalogue-fault")

    event.listen(database.sync_engine, "before_cursor_execute", unavailable)
    try:
        response = await getattr(clients[0], "post" if path == "disconnect" else "get")(
            "/api/twitch/" + path
        )
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", unavailable)
        await _close_application_twitch(app)
    assert seen and response.status_code == 200
    body = response.json()
    if path == "connection-status":
        assert body == {
            "connected": False,
            "valid": False,
            "expires_at": None,
            "source": None,
            "has_env_token": False,
        }
    else:
        assert body == {"success": False, "message": "Failed to disconnect"}
    assert "synthetic-twitch-catalogue-fault" not in response.text
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload,detail",
    [
        ("manual-token", {"token": "   "}, "Invalid Twitch OAuth token"),
        ("import-streamers", [], "No streamers provided"),
    ],
)
async def test_empty_twitch_mutation_is_rejected_without_catalogue_changes(
    proxy_applications, path, payload, detail
):
    apps, databases, clients, _ = proxy_applications
    app, database = apps[0], databases[0]
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app}),
    )
    before = await service.get_state()
    try:
        response = await clients[0].post("/api/twitch/" + path, json=payload)
        assert response.status_code == 400 and detail in response.text
        assert await service.get_state() == before
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        if app.state.recording_manager is not None:
            await app.state.recording_manager.shutdown()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await _close_application_logging(app)
