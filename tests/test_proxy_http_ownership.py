"""Authenticated proxy APIs use closed, off-loop catalogue scopes of their factory."""

from threading import get_ident
from hashlib import sha256

from cryptography.fernet import Fernet
import pytest

from app.lifespan import _close_application_proxy
from app.models import GlobalSettings, ProxySettings, RecordingSettings
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


def identity_fingerprint(database):
    with database.sync_session_factory() as session:
        return sha256(
            session.query(GlobalSettings).first().proxy_encryption_key.encode()
        ).hexdigest()


@pytest.fixture
async def proxy_applications(image_applications):
    applications, databases, clients, queries = image_applications
    try:
        for index, database in enumerate(databases):
            with database.sync_session_factory() as session:
                settings = session.query(GlobalSettings).first()
                if settings is None:
                    settings = GlobalSettings(
                        proxy_encryption_key=Fernet.generate_key().decode()
                    )
                    session.add(settings)
                elif not settings.proxy_encryption_key:
                    settings.proxy_encryption_key = Fernet.generate_key().decode()
                session.flush()
                proxy = ProxySettings(
                    id=1, enabled=True, health_status="healthy", priority=index
                )
                session.add(proxy)
                proxy.proxy_url = f"http://owner-{index}.invalid:8080"
                session.add(
                    RecordingSettings(
                        enable_proxy=True,
                        proxy_health_check_interval_seconds=60 + index,
                    )
                )
                session.commit()
        fingerprints = [
            await run_in_thread_pool(identity_fingerprint, database)
            for database in databases
        ]
        yield applications, databases, clients, queries
        assert [
            await run_in_thread_pool(identity_fingerprint, database)
            for database in databases
        ] == fingerprints
    finally:
        for app in applications:
            await _close_application_proxy(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["list", "config", "best"])
async def test_proxy_read_apis_project_the_owning_catalogue_off_loop(
    proxy_applications, path
):
    _, databases, clients, queries = proxy_applications
    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get(f"/api/proxy/{path}")
        assert response.status_code == 200
        payload = response.json()
        if path == "config":
            assert payload["proxy_health_check_interval_seconds"] == 60 + index
        elif path == "list":
            assert payload["proxies"][0]["proxy_url"] == f"owner-{index}.invalid:8080"
            assert (
                payload["system_config"]["proxy_health_check_interval_seconds"]
                == 60 + index
            )
        else:
            assert payload["proxy"]["proxy_url"] == f"owner-{index}.invalid:8080"
        workers = [
            thread
            for thread, sql in queries
            if "FROM proxy_settings" in sql or "FROM recording_settings" in sql
        ]
        assert workers and get_ident() not in workers
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("DELETE", "/1", None),
        ("POST", "/1/update-priority", {"priority": -2}),
        (
            "POST",
            "/config/update?enable_proxy=false&proxy_health_check_interval_seconds=90",
            None,
        ),
    ],
)
async def test_proxy_sql_mutations_commit_only_the_owned_catalogue_off_loop(
    proxy_applications, method, path, body
):
    _, databases, clients, queries = proxy_applications
    queries.clear()
    response = await clients[0].request(method, "/api/proxy" + path, json=body)
    assert response.status_code == 200
    assert response.json()["success"] is True
    workers = [
        thread
        for thread, sql in queries
        if "proxy_settings" in sql or "recording_settings" in sql
    ]
    assert workers and get_ident() not in workers
    own = (await clients[0].get("/api/proxy/list")).json()
    peer = (await clients[1].get("/api/proxy/list")).json()
    assert len(peer["proxies"]) == 1 and peer["proxies"][0]["priority"] == 1
    assert peer["system_config"]["enable_proxy"] is True
    assert peer["system_config"]["proxy_health_check_interval_seconds"] == 61
    if method == "DELETE":
        assert own["proxies"] == []
    elif "update-priority" in path:
        assert own["proxies"][0]["priority"] == -2
    else:
        assert own["system_config"]["enable_proxy"] is False
        assert own["system_config"]["proxy_health_check_interval_seconds"] == 90
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["add", "toggle", "test"])
async def test_proxy_health_api_background_work_has_an_owner_and_no_orm_handoff(
    proxy_applications, monkeypatch, action
):
    applications, databases, clients, queries = proxy_applications
    from pydantic import SecretStr

    for app in applications:
        app.state.settings.TWITCH_APP_ID = ""
        app.state.settings.twitch_app_secret = SecretStr("")
    sent = []
    manager = applications[0].state.websocket_manager
    native_send = manager.send_notification

    async def observe(message):
        sent.append(message)
        await native_send(message)

    monkeypatch.setattr(manager, "send_notification", observe)
    queries.clear()
    path = "/api/proxy/add" if action == "add" else f"/api/proxy/1/{action}"
    body = (
        {"proxy_url": "http://new.invalid:8080", "priority": 8}
        if action == "add"
        else None
    )
    response = await clients[0].post(path, json=body)
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(sent) == 1
    notice = sent[0]
    assert notice["type"] == "proxy_health_update"
    assert notice["proxy"]["enabled"] is (action != "toggle")
    workers = [
        thread
        for thread, sql in queries
        if "proxy_settings" in sql or "recording_settings" in sql
    ]
    assert workers and get_ident() not in workers
    own = (await clients[0].get("/api/proxy/list")).json()["proxies"]
    peer = (await clients[1].get("/api/proxy/list")).json()["proxies"]
    assert (
        len(peer) == 1
        and peer[0]["health_status"] == "healthy"
        and peer[0]["enabled"] is True
    )
    if action == "add":
        assert len(own) == 2
        assert own[1]["proxy_url"] == "new.invalid:8080"
        assert own[1]["health_status"] == "failed"
        duplicate = await clients[0].post(path, json=body)
        assert duplicate.status_code == 400
        assert len((await clients[0].get("/api/proxy/list")).json()["proxies"]) == 2
    elif action == "toggle":
        assert own[0]["enabled"] is False
    else:
        assert (
            own[0]["health_status"] == "failed" and own[0]["consecutive_failures"] == 1
        )
    assert applications[0].state.proxy_health_service._supervisor.failures == ()
    assert applications[0].state.proxy_health_service._supervisor.task_names == ()
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body,status",
    [
        ("POST", "/add", {"proxy_url": "ftp://invalid.example"}, 422),
        (
            "POST",
            "/config/update?enable_proxy=false&proxy_health_check_interval_seconds=59",
            None,
            400,
        ),
        (
            "POST",
            "/config/update?enable_proxy=false&proxy_max_consecutive_failures=0",
            None,
            400,
        ),
        (
            "POST",
            "/config/update?enable_proxy=false&proxy_max_consecutive_failures=11",
            None,
            400,
        ),
        ("DELETE", "/999", None, 404),
        ("POST", "/999/toggle", None, 404),
        ("POST", "/999/update-priority", {"priority": 3}, 404),
        ("POST", "/999/test", None, 404),
    ],
)
async def test_proxy_api_rejections_leave_both_catalogues_unchanged(
    proxy_applications, method, path, body, status
):
    _, databases, clients, _ = proxy_applications
    before = [(await client.get("/api/proxy/list")).json() for client in clients]
    response = await clients[0].request(method, "/api/proxy" + path, json=body)
    assert response.status_code == status
    assert [
        (await client.get("/api/proxy/list")).json() for client in clients
    ] == before
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
async def test_proxy_add_request_cancellation_drains_its_background_health_action(
    proxy_applications,
):
    import asyncio
    from pydantic import SecretStr
    from app import dependencies
    from app.utils.async_db_utils import run_in_thread_pool
    from tests.test_proxy_managed_http_ownership import origin

    applications, databases, clients, _ = proxy_applications
    settings = applications[0].state.settings
    settings.TWITCH_APP_ID = "owned-cancel"
    settings.twitch_app_secret = SecretStr("synthetic-cancel-secret")
    service = await run_in_thread_pool(
        dependencies._get_application_proxy_health_service, applications[0]
    )
    async with origin() as (url, _, entered, _):
        service.token_endpoint = url + "/hold"
        request = asyncio.create_task(
            clients[0].post(
                "/api/proxy/add",
                json={"proxy_url": "http://new.invalid:8080", "priority": 8},
            )
        )
        try:
            await asyncio.wait_for(entered.wait(), 2)
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            assert service._supervisor.task_names == ()
            assert not service._proxy_clients
            own = (await clients[0].get("/api/proxy/list")).json()["proxies"]
            assert len(own) == 2 and own[1]["health_status"] == "unknown"
            assert own[1]["consecutive_failures"] == 0
            peer = (await clients[1].get("/api/proxy/list")).json()["proxies"]
            assert len(peer) == 1 and peer[0]["health_status"] == "healthy"
            assert all(
                database.sync_engine.pool.checkedout() == 0 for database in databases
            )
        finally:
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)


@pytest.mark.asyncio
async def test_proxy_mutations_reject_anonymous_requests_without_effects(
    proxy_applications,
):
    applications, _, clients, _ = proxy_applications
    before = (await clients[0].get("/api/proxy/list")).json()
    clients[0].cookies.clear()
    for method, path, body in [
        ("GET", "/list", None),
        ("POST", "/add", {"proxy_url": "http://new.invalid:8080"}),
        ("DELETE", "/1", None),
    ]:
        response = await clients[0].request(
            method,
            "/api/proxy" + path,
            json=body,
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 401
    browser_response = await clients[0].get("/api/proxy/list")
    assert browser_response.status_code == 307
    assert browser_response.headers["location"] == "/auth/login"
    assert applications[0].state.proxy_health_service is None
    with applications[0].state.database_lifecycle.sync_session_factory() as session:
        assert session.query(ProxySettings).count() == len(before["proxies"])
        assert session.get(ProxySettings, 1).enabled is True
