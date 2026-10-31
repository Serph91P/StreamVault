"""Real application admin boundary: current policy and no forbidden effects."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from fastapi.routing import iter_route_contexts
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_auth_service, get_db, require_admin_user
from app.main import create_app
from app.models import User
from app.services.core.api_key_service import ApiKeyService
from app.services.core.auth_service import AuthService
from app.services.background_queue_cleanup_service import BackgroundQueueCleanupService
from app.utils.token_store import ShareTokenModel


@pytest.fixture
def admin_stack(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        AUTH_JWT_SECRET="admin-policy-test-secret-at-least-thirty-two-characters",
        AUTH_JWT_ALGORITHM="HS256",
        AUTH_JWT_ISSUER="admin-policy-test",
        AUTH_JWT_AUDIENCE="admin-policy-api",
        AUTH_ACCESS_TOKEN_MINUTES=15,
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        with factory() as db:
            yield db

    def test_auth(db=Depends(get_db)):
        return AuthService(db, settings=settings)

    import app.database as database
    import app.middleware.auth as middleware
    import app.config.settings as config
    import app.routes.admin as admin

    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(middleware, "SessionLocal", factory)
    monkeypatch.setattr(middleware, "AuthService", lambda db: AuthService(db, settings))
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(RECORDING_DIRECTORY=str(tmp_path)),
    )
    # Only disposable local paths pass this test's filesystem boundary.
    import app.utils.security as security

    def local_path(path, _operation):
        assert Path(path).resolve().is_relative_to(tmp_path)
        return path

    monkeypatch.setattr(security, "validate_path_security", local_path)
    queue = SimpleNamespace(
        external_tasks={
            "synthetic-job": SimpleNamespace(
                task_type="recording", progress=100, status="running"
            )
        },
        active_tasks={},
    )
    monkeypatch.setattr(admin, "_background_queue_service", queue)
    import app.services.background_queue_cleanup_service as cleanup

    monkeypatch.setattr(
        cleanup, "get_cleanup_service", lambda: BackgroundQueueCleanupService(queue)
    )
    with factory() as db:
        db.add(
            User(
                username="setup-admin", password="unused", is_admin=True, is_active=True
            )
        )
        db.add(
            ShareTokenModel(
                id=1,
                token="synthetic-share",
                stream_id=1,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    sentinel = tmp_path / "recording.ts"
    sentinel.write_bytes(b"synthetic recording")
    app = create_app(
        settings=settings,
        service_overrides={get_db: test_db, get_auth_service: test_auth},
    )
    # No lifespan: no provider connections, schedulers or startup cleanup.
    yield app, settings, factory, sentinel, queue
    engine.dispose()


def credential_headers(stack, mode, state):
    _app, settings, factory, _sentinel, _queue = stack
    headers = {"accept": "application/json"}
    if state == "anonymous":
        return headers
    with factory() as db:
        user = User(
            username=f"{mode}-{state}",
            password="unused",
            is_active=True,
            is_admin=state != "nonadmin",
        )
        db.add(user)
        db.commit()
        service = AuthService(db, settings)
        if mode in {"jwt", "cookie"}:
            token = service.create_access_token(user)
            headers.update(
                {"Authorization": f"Bearer {token}"}
                if mode == "jwt"
                else {"Cookie": f"access_token={token}"}
            )
        elif mode.startswith("legacy"):
            token = asyncio.run(service.create_session(user.id))
            headers.update(
                {"Cookie": f"session={token}"}
                if mode == "legacy"
                else {"Authorization": f"Bearer {token}"}
            )
        else:
            _, token = ApiKeyService(db).create(user.id, "admin policy")
            headers.update(
                {"X-API-Key": token}
                if mode == "api-key"
                else {"Authorization": f"ApiKey {token}"}
            )
        if state == "disabled":
            user.is_active = False
        elif state == "demoted":
            user.is_admin = False
        db.commit()
    return headers


MODES = ["jwt", "cookie", "legacy", "legacy-bearer", "api-key", "api-key-authorization"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "state", ["anonymous", "nonadmin", "admin", "disabled", "demoted"]
)
def test_admin_current_policy_before_database_and_file_effects(
    admin_stack, mode, state
):
    app, _settings, factory, sentinel, queue = admin_stack
    headers = credential_headers(admin_stack, mode, state)
    expected = 200 if state == "admin" else 403
    if state in {"anonymous", "disabled"} or (
        state == "demoted" and mode in {"jwt", "cookie"}
    ):
        expected = 401

    def business_snapshot():
        with factory() as db:
            return {
                table.name: [
                    tuple(row)
                    for row in db.execute(
                        select(
                            *[
                                column
                                for column in table.columns
                                if not (
                                    table.name == "api_keys"
                                    and column.name == "last_used_at"
                                )
                            ]
                        )
                    )
                ]
                for table in Base.metadata.sorted_tables
            }

    before = business_snapshot()
    client = TestClient(app)
    try:
        read = client.get("/api/admin/tests/available", headers=headers)
        deleted = client.delete("/api/admin/share-tokens/1", headers=headers)
        cleanup = client.post("/api/admin/maintenance/cleanup-temp", headers=headers)
        jobs = client.post(
            "/api/admin/background-queue/cleanup/stuck-recordings", headers=headers
        )
        assert [
            read.status_code,
            deleted.status_code,
            cleanup.status_code,
            jobs.status_code,
        ] == [expected] * 4
        with factory() as db:
            assert (db.get(ShareTokenModel, 1) is None) == (state == "admin")
        assert sentinel.exists() == (state != "admin")
        assert queue.external_tasks["synthetic-job"].status == (
            "completed" if state == "admin" else "running"
        )
        assert queue.active_tasks == {}
        if state != "admin":
            assert business_snapshot() == before
            assert sentinel.read_bytes() == b"synthetic recording"
    finally:
        client.close()


def test_every_mounted_admin_operation_has_current_user_guard(admin_stack):
    app, *_ = admin_stack
    operations = []
    for context in iter_route_contexts(app.routes):
        if context.path.startswith(("/api/admin/", "/admin/")):
            assert require_admin_user in [
                dependency.call for dependency in context.dependant.dependencies
            ], context.path
            operations.extend((context.path, method) for method in context.methods)
    assert ("/api/admin/share-tokens/{token_id}", "DELETE") in operations
    assert ("/api/admin/post-processing/retry-specific", "POST") in operations
    assert ("/admin/websocket-connections", "GET") in operations


@pytest.mark.parametrize("mode", MODES)
def test_nested_admin_and_monitoring_policy_before_body_validation(admin_stack, mode):
    app, *_ = admin_stack
    client = TestClient(app)
    try:
        for state, expected in [("nonadmin", 403), ("admin", 200)]:
            headers = credential_headers(admin_stack, mode, state)
            monitoring = client.get("/admin/websocket-connections", headers=headers)
            nested = client.post(
                "/api/admin/post-processing/retry-specific", headers=headers, json={}
            )
            assert monitoring.status_code == expected
            assert nested.status_code == (422 if state == "admin" else 403)
        assert (
            client.put("/api/admin/tests/available", headers=headers).status_code == 405
        )
    finally:
        client.close()


@pytest.mark.parametrize("mode", ["cookie", "legacy"])
def test_admin_cookie_mutation_retains_csrf_boundary(admin_stack, mode):
    app, *_ = admin_stack
    headers = credential_headers(admin_stack, mode, "admin")
    client = TestClient(app)
    try:
        response = client.delete(
            "/api/admin/share-tokens/1",
            headers=headers | {"origin": "https://foreign.invalid"},
        )
        assert response.status_code == 403
        assert response.json() == {"error": "CSRF validation failed"}
        assert (
            client.delete(
                "/api/admin/share-tokens/1",
                headers=headers | {"origin": "http://testserver"},
            ).status_code
            == 200
        )
    finally:
        client.close()
