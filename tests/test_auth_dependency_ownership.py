"""Authenticated dependency projections release SQL before controller publication."""

import pytest
from dataclasses import FrozenInstanceError, is_dataclass
from pydantic import SecretStr
from sqlalchemy import inspect
from starlette.requests import Request

from app import dependencies
from app.models import User
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
async def test_current_user_dependency_releases_its_pool_before_proxy_publication(
    proxy_applications, monkeypatch
):
    applications, databases, clients, _ = proxy_applications
    app = applications[0]
    app.state.settings.TWITCH_APP_ID = ""
    app.state.settings.twitch_app_secret = SecretStr("")
    manager = app.state.websocket_manager
    native_send = manager.send_notification
    observed = []

    async def publish(message):
        observed.append([db.sync_engine.pool.checkedout() for db in databases])
        await native_send(message)

    monkeypatch.setattr(manager, "send_notification", publish)
    response = await clients[0].post("/api/proxy/1/test")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert observed == [[0, 0]]
    own = (await clients[0].get("/api/proxy/list")).json()["proxies"]
    peer = (await clients[1].get("/api/proxy/list")).json()["proxies"]
    assert own[0]["health_status"] == "failed"
    assert own[0]["consecutive_failures"] == 1
    assert peer[0]["health_status"] == "healthy"
    assert peer[0]["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_current_user_is_a_frozen_owner_value_not_a_detached_orm_model(
    proxy_applications,
):
    applications, databases, clients, _ = proxy_applications
    for index, app in enumerate(applications):

        def rename():
            with databases[index].sync_session_factory() as session:
                session.query(User).one().username = f"fixture-owner-{index}"
                session.commit()

        await run_in_thread_pool(rename)
        request = Request(
            {
                "type": "http",
                "app": app,
                "headers": [
                    (
                        b"cookie",
                        f"access_token={clients[index].cookies.get('access_token')}".encode(),
                    )
                ],
            }
        )
        factory = databases[index].sync_session_factory
        identity = await run_in_thread_pool(
            dependencies.get_current_identity, request, session_factory=factory
        )
        user = await run_in_thread_pool(
            dependencies.get_current_user, identity, session_factory=factory
        )
        assert is_dataclass(user)
        assert inspect(user, raiseerr=False) is None
        assert user.username == f"fixture-owner-{index}"
        assert user.is_active and user.is_admin
        with pytest.raises(FrozenInstanceError):
            setattr(user, "username", "fixture-mutation")
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
