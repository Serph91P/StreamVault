"""Auth SQL/Argon work stays in native workers; login budgets stay app-owned."""

import asyncio
from contextlib import AsyncExitStack
from secrets import token_urlsafe
from threading import get_ident

from argon2 import PasswordHasher
import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.routes import auth


@pytest.fixture
async def auth_applications(tmp_path, monkeypatch):
    applications, databases, clients, queries, hashes = [], [], [], [], []
    auth._login_attempts.clear()
    native_hash, native_verify = PasswordHasher.hash, PasswordHasher.verify

    def hash(self, *args, **kwargs):
        hashes.append(("hash", get_ident()))
        return native_hash(self, *args, **kwargs)

    def verify(self, *args, **kwargs):
        hashes.append(("verify", get_ident()))
        return native_verify(self, *args, **kwargs)

    monkeypatch.setattr(PasswordHasher, "hash", hash)
    monkeypatch.setattr(PasswordHasher, "verify", verify)
    async with AsyncExitStack() as stack:
        try:
            for index in range(2):
                database = DatabaseLifecycle(
                    f"sqlite:///{tmp_path / (str(index) + '.db')}"
                )
                databases.append(database)
                with database.sync_engine.begin() as connection:
                    Base.metadata.create_all(connection)
                application = create_app(
                    settings=Settings(
                        ENVIRONMENT="test",
                        auth_jwt_secret=SecretStr(token_urlsafe(48)),
                        RECORDING_DIRECTORY=str(tmp_path / str(index)),
                        _env_file=None,
                    ),
                    database=database,
                )
                applications.append(application)
                event.listen(
                    database.sync_engine,
                    "before_cursor_execute",
                    lambda *_: queries.append(get_ident()),
                )
                client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        transport=httpx.ASGITransport(
                            app=application, client=("198.51.100.84", 842)
                        ),
                        base_url="https://localhost:8000",
                        headers={"Accept": "application/json"},
                    )
                )
                clients.append(client)
                credentials = {
                    "username": "auth-admin",
                    "password": "synthetic-native-auth-password",
                }
                assert (
                    await client.post("/auth/setup", json=credentials)
                ).status_code == 200
                assert (
                    await client.post("/auth/login", json=credentials)
                ).status_code == 200
            yield applications, databases, clients, queries, hashes
        finally:
            auth._login_attempts.clear()
            for application in applications:
                await application.state.websocket_manager.close_all()
            for database in databases:
                await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,status",
    [
        ("GET", "/auth/setup", 200),
        ("GET", "/auth/login", 200),
        ("GET", "/auth/check", 200),
        ("POST", "/auth/refresh", 200),
        ("POST", "/auth/setup", 400),
        ("POST", "/auth/logout", 200),
    ],
)
async def test_real_auth_sql_is_off_loop_and_returns_closed_scope(
    auth_applications, method, path, status
):
    _, databases, clients, queries, _ = auth_applications
    for client in clients:
        queries.clear()
        body = (
            {"username": "other", "password": "synthetic-native-other-password"}
            if path == "/auth/setup" and method == "POST"
            else None
        )
        response = await client.request(method, path, json=body)
        assert response.status_code == status, response.text
        assert queries and get_ident() not in queries
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_real_setup_and_login_argon_work_is_not_on_the_loop(auth_applications):
    _, databases, clients, queries, hashes = auth_applications
    assert {operation for operation, _ in hashes} == {"hash", "verify"}
    assert get_ident() not in [thread for _, thread in hashes]
    assert queries and get_ident() not in queries
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
async def test_login_failure_budget_does_not_leak_between_factories(auth_applications):
    _, _, clients, _, _ = auth_applications
    credentials = {
        "username": "missing-budget-user",
        "password": "synthetic-wrong-password",
    }
    for _ in range(5):
        assert (
            await clients[0].post("/auth/login", json=credentials)
        ).status_code == 401
    blocked = await clients[0].post("/auth/login", json=credentials)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert (await clients[1].post("/auth/login", json=credentials)).status_code == 401


@pytest.mark.asyncio
async def test_native_concurrent_failures_preserve_exact_login_budget(
    auth_applications,
):
    _, _, clients, _, _ = auth_applications
    credentials = {
        "username": "missing-budget-user",
        "password": "synthetic-wrong-password",
    }
    responses = await asyncio.gather(
        *(clients[0].post("/auth/login", json=credentials) for _ in range(8))
    )
    statuses = [response.status_code for response in responses]
    assert statuses.count(401) == 5
    assert statuses.count(429) == 3


@pytest.mark.asyncio
async def test_legacy_check_and_keepalive_stay_native_and_app_bound(auth_applications):
    _, databases, clients, queries, _ = auth_applications
    for client in clients:
        for cookie in list(client.cookies.jar):
            if cookie.name in {"access_token", "refresh_token"}:
                client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
        queries.clear()
        assert (await client.get("/auth/check")).json() == {"authenticated": True}
        assert (await client.post("/auth/keepalive")).json() == {"ok": True}
        assert queries and get_ident() not in queries
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_native_first_admin_admission_is_serialized(tmp_path):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'admission.db'}")
    with database.sync_engine.begin() as connection:
        Base.metadata.create_all(connection)
    application = create_app(
        settings=Settings(
            ENVIRONMENT="test",
            auth_jwt_secret=SecretStr(token_urlsafe(48)),
            _env_file=None,
        ),
        database=database,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="https://localhost:8000",
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.post(
                        "/auth/setup",
                        json={
                            "username": f"admin-{index}",
                            "password": "synthetic-native-setup-password",
                        },
                    )
                    for index in range(4)
                )
            )
        statuses = [response.status_code for response in responses]
        assert statuses.count(200) == 1
        assert statuses.count(400) == 3
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await application.state.websocket_manager.close_all()
        await database.adispose()
