"""End-to-end compatibility contracts for JWT and legacy authentication."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, FastAPI, WebSocket
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.database import Base
from app.models import ApiKey, RefreshToken, Session, User
from app.services.core.auth_service import AuthService
from app.services.core.api_key_service import ApiKeyService
from app.dependencies import get_auth_service, get_current_user, get_db, require_scopes
from app.middleware.auth import AuthMiddleware
from app.routes import auth as auth_routes


@pytest.fixture
def auth_stack(monkeypatch):
    settings = SimpleNamespace(
        AUTH_JWT_SECRET="middleware-test-secret-which-is-long-enough-to-be-secure-123456",
        AUTH_JWT_ALGORITHM="HS256",
        AUTH_JWT_ISSUER="streamvault-test",
        AUTH_JWT_AUDIENCE="streamvault-test-api",
        AUTH_ACCESS_TOKEN_MINUTES=15,
        AUTH_REFRESH_TOKEN_HOURS=24,
        AUTH_REFRESH_FAMILY_MAX_HOURS=168,
        USE_SECURE_COOKIES=False,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            RefreshToken.__table__,
            Session.__table__,
            ApiKey.__table__,
        ],
    )
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionFactory() as db:
        service = AuthService(db, settings=settings)
        user = User(
            username="middleware-admin",
            password=service.hash_password("correct horse"),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        user_id = user.id
        legacy_token = asyncio.run(service.create_session(user.id))
        _, api_key = ApiKeyService(db).create(user.id, "middleware contract")

    def get_test_db():
        db = SessionFactory()
        try:
            yield db
        finally:
            db.close()

    def get_test_auth_service():
        return AuthService(SessionFactory(), settings=settings)

    import app.middleware.auth as auth_middleware

    monkeypatch.setattr(auth_middleware, "SessionLocal", SessionFactory)
    monkeypatch.setattr(
        auth_middleware,
        "AuthService",
        lambda db: AuthService(db, settings=settings),
    )
    monkeypatch.setattr(auth_routes, "get_settings", lambda: settings)

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/auth")

    @app.get("/api/settings")
    async def settings_endpoint(
        user=Depends(get_current_user),
        _identity=Depends(require_scopes("settings:read")),
    ):
        return {"user_id": user.id}

    @app.get("/api/api-key-compatible")
    async def api_key_compatible_endpoint():
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"ok": True})
        await websocket.close()

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_auth_service] = get_test_auth_service
    app.add_middleware(AuthMiddleware)

    try:
        yield app, settings, SessionFactory, user_id, legacy_token, api_key
    finally:
        Base.metadata.drop_all(
            engine,
            tables=[
                ApiKey.__table__,
                Session.__table__,
                RefreshToken.__table__,
                User.__table__,
            ],
        )
        engine.dispose()


def _access_token(settings, user_id: int, *, expires_at: datetime | None = None) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "typ": "access",
            "jti": "middleware-contract",
            "iat": now,
            "nbf": now,
            "exp": expires_at or now + timedelta(minutes=5),
            "iss": settings.AUTH_JWT_ISSUER,
            "aud": settings.AUTH_JWT_AUDIENCE,
            "roles": ["admin"],
            "scp": ["settings:read"],
        },
        settings.AUTH_JWT_SECRET,
        algorithm="HS256",
    )


def test_login_access_cookie_and_bearer_jwt_reach_protected_settings(auth_stack):
    app, settings, _SessionFactory, user_id, _legacy_token, _api_key = auth_stack

    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "middleware-admin", "password": "correct horse"},
        )
        cookie_response = client.get(
            "/api/settings", headers={"accept": "application/json"}
        )

    assert login.status_code == 200
    assert "access_token" in login.cookies
    assert cookie_response.status_code == 200
    assert cookie_response.json() == {"user_id": user_id}

    with TestClient(app) as client:
        bearer_response = client.get(
            "/api/settings",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {_access_token(settings, user_id)}",
            },
        )

    assert bearer_response.status_code == 200
    assert bearer_response.json() == {"user_id": user_id}


def test_invalid_expired_and_disabled_jwts_fail_closed(auth_stack):
    app, settings, SessionFactory, user_id, _legacy_token, _api_key = auth_stack

    with TestClient(app) as client:
        client.cookies.set("access_token", "not-a-jwt")
        malformed = client.get("/api/settings", headers={"accept": "application/json"})
        malformed_bearer = client.get(
            "/api/settings",
            headers={"accept": "application/json", "Authorization": "Bearer not-a-jwt"},
        )
        client.cookies.set(
            "access_token",
            _access_token(
                settings,
                user_id,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            ),
        )
        expired = client.get("/api/settings", headers={"accept": "application/json"})

    with SessionFactory() as db:
        db.query(User).filter_by(id=user_id).update({User.is_active: False})
        db.commit()

    with TestClient(app) as client:
        disabled = client.get(
            "/api/settings",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {_access_token(settings, user_id)}",
            },
        )

    assert malformed.status_code == 401
    assert malformed_bearer.status_code == 401
    assert expired.status_code == 401
    assert disabled.status_code == 401


def test_legacy_session_and_api_key_remain_compatible(auth_stack):
    app, _settings, _SessionFactory, user_id, legacy_token, api_key = auth_stack

    with TestClient(app) as client:
        client.cookies.set("session", legacy_token)
        legacy = client.get("/api/settings", headers={"accept": "application/json"})

    with TestClient(app) as client:
        legacy_bearer = client.get(
            "/api/settings",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {legacy_token}",
            },
        )

    with TestClient(app) as client:
        api_key_response = client.get(
            "/api/api-key-compatible",
            headers={"accept": "application/json", "X-API-Key": api_key},
        )
        invalid_api_key_response = client.get(
            "/api/api-key-compatible",
            headers={
                "accept": "application/json",
                "X-API-Key": "sv_invalid_middleware_contract",
            },
        )

    assert legacy.status_code == 200
    assert legacy.json() == {"user_id": user_id}
    assert legacy_bearer.status_code == 200
    assert legacy_bearer.json() == {"user_id": user_id}
    assert api_key_response.status_code == 200
    assert api_key_response.json() == {"ok": True}
    assert invalid_api_key_response.status_code == 401
    assert invalid_api_key_response.json() == {
        "error": "Authentication required",
        "redirect": "/auth/login",
    }


def test_websocket_accepts_access_cookie_or_bearer_and_rejects_invalid_jwt(auth_stack):
    app, settings, _SessionFactory, user_id, legacy_token, _api_key = auth_stack
    token = _access_token(settings, user_id)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws", headers={"Cookie": f"access_token={token}"}
        ) as websocket:
            assert websocket.receive_json() == {"ok": True}

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws", headers={"Authorization": f"Bearer {token}"}
        ) as websocket:
            assert websocket.receive_json() == {"ok": True}

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws", headers={"Authorization": f"Bearer {legacy_token}"}
        ) as websocket:
            assert websocket.receive_json() == {"ok": True}

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect(
                "/ws", headers={"Authorization": "Bearer invalid"}
            ) as websocket:
                websocket.receive_json()

    assert rejected.value.code == 4001


def test_expired_access_cookie_can_reach_refresh_endpoint(auth_stack):
    app, settings, _SessionFactory, user_id, _legacy_token, _api_key = auth_stack

    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "middleware-admin", "password": "correct horse"},
        )
        client.cookies.set(
            "access_token",
            _access_token(
                settings,
                user_id,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            ),
        )
        refresh = client.post("/auth/refresh", headers={"accept": "application/json"})

    assert login.status_code == 200
    assert refresh.status_code == 200
    assert "access_token" in refresh.cookies


def test_auth_check_rejects_a_disabled_jwt_subject(auth_stack):
    app, settings, SessionFactory, user_id, _legacy_token, _api_key = auth_stack

    with SessionFactory() as db:
        db.query(User).filter_by(id=user_id).update({User.is_active: False})
        db.commit()

    with TestClient(app) as client:
        client.cookies.set("access_token", _access_token(settings, user_id))
        checked = client.get("/auth/check", headers={"accept": "application/json"})

    assert checked.status_code == 200
    assert checked.json() == {"authenticated": False}
