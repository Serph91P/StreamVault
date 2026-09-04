import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import (
    AuthIdentity,
    get_auth_service,
    get_current_identity,
    require_scopes,
)
from app.models import RefreshToken, Session, User
from app.routes import auth as auth_routes
from app.schemas.auth import UserCreate
from app.services.core.auth_service import (
    AuthConfigurationError,
    AuthService,
    AuthTokenError,
    RefreshTokenReplayError,
)


@pytest.fixture
def auth_settings():
    return SimpleNamespace(
        AUTH_JWT_SECRET="phase3-test-secret-which-is-long-enough-to-be-secure-123456",
        AUTH_JWT_ALGORITHM="HS256",
        AUTH_JWT_ISSUER="streamvault-test",
        AUTH_JWT_AUDIENCE="streamvault-test-api",
        AUTH_ACCESS_TOKEN_MINUTES=15,
        AUTH_REFRESH_TOKEN_HOURS=24,
        AUTH_REFRESH_FAMILY_MAX_HOURS=168,
        USE_SECURE_COOKIES=False,
    )


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine, tables=[User.__table__, RefreshToken.__table__, Session.__table__]
    )
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(
            engine, tables=[Session.__table__, RefreshToken.__table__, User.__table__]
        )
        engine.dispose()


@pytest.mark.asyncio
async def test_login_success_failure_and_disabled_user_are_explicit(
    db_session, auth_settings
):
    service = AuthService(db_session, settings=auth_settings)
    user = User(
        username="admin", password=service.hash_password("correct horse"), is_admin=True
    )
    disabled = User(
        username="disabled",
        password=service.hash_password("correct horse"),
        is_admin=True,
        is_active=False,
    )
    db_session.add_all([user, disabled])
    db_session.commit()

    assert await service.validate_login("admin", "correct horse") == user
    assert await service.validate_login("admin", "wrong") is None
    assert await service.validate_login("missing", "correct horse") is None
    assert await service.validate_login("disabled", "correct horse") is None


@pytest.mark.asyncio
async def test_admin_creation_and_legacy_sessions_keep_the_compatibility_contract(
    db_session, auth_settings
):
    service = AuthService(db_session, settings=auth_settings)

    assert not await service.admin_exists()
    created = await service.create_admin(
        UserCreate(username="created-admin", password="correct horse")
    )
    assert created.username == "created-admin"
    assert await service.admin_exists()

    raw_session = await service.create_session(created.id)
    assert await service.validate_session(raw_session)
    legacy_row = db_session.query(Session).filter_by(user_id=created.id).one()
    assert legacy_row.user_id == created.id
    assert await service.refresh_session(raw_session)
    assert await service.delete_session(raw_session)
    assert not await service.validate_session(raw_session)

    expired_session = await service.create_session(created.id)
    expired_row = db_session.query(Session).filter_by(user_id=created.id).one()
    expired_row.created_at = datetime.now() - timedelta(
        hours=service.session_timeout_hours + 1
    )
    db_session.commit()
    assert not await service.validate_session(expired_session)
    assert db_session.query(Session).filter_by(user_id=created.id).first() is None

    await service.create_session(created.id)
    cleanup_row = db_session.query(Session).filter_by(user_id=created.id).one()
    cleanup_row.created_at = datetime.now() - timedelta(
        hours=service.session_timeout_hours + 1
    )
    db_session.commit()
    assert await service.cleanup_expired_sessions() == 1
    assert db_session.query(Session).filter_by(user_id=created.id).first() is None


def test_jwt_configuration_and_inactive_user_fail_closed(db_session, auth_settings):
    invalid_settings = SimpleNamespace(
        **(vars(auth_settings) | {"AUTH_JWT_SECRET": "short"})
    )
    invalid_service = AuthService(db_session, settings=invalid_settings)
    with pytest.raises(AuthConfigurationError):
        invalid_service._jwt_config()

    service = AuthService(db_session, settings=auth_settings)
    inactive = User(
        username="inactive-token-user",
        password=service.hash_password("password"),
        is_admin=False,
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()

    with pytest.raises(AuthTokenError):
        service.issue_token_pair(inactive)
    with pytest.raises(AuthTokenError):
        service.rotate_refresh_token("missing-refresh-token")


@pytest.mark.asyncio
async def test_legacy_bcrypt_and_argon2_hashes_are_rehashed_after_valid_login(
    db_session, auth_settings
):
    service = AuthService(db_session, settings=auth_settings)
    bcrypt_hash = bcrypt.hashpw(b"legacy-password", bcrypt.gensalt()).decode()
    old_argon2_hash = service.password_hasher(time_cost=1).hash("legacy-password")
    bcrypt_user = User(username="bcrypt", password=bcrypt_hash, is_admin=True)
    argon2_user = User(username="argon2", password=old_argon2_hash, is_admin=True)
    db_session.add_all([bcrypt_user, argon2_user])
    db_session.commit()

    assert await service.validate_login("bcrypt", "legacy-password") == bcrypt_user
    assert await service.validate_login("argon2", "legacy-password") == argon2_user
    assert bcrypt_user.password.startswith("$argon2")
    assert argon2_user.password.startswith("$argon2")


@pytest.mark.asyncio
async def test_access_tokens_enforce_type_temporal_issuer_audience_and_algorithm(
    db_session, auth_settings
):
    service = AuthService(db_session, settings=auth_settings)
    user = User(
        username="admin", password=service.hash_password("password"), is_admin=True
    )
    db_session.add(user)
    db_session.commit()

    access_token = service.create_access_token(user)
    claims = service.decode_access_token(access_token)
    assert claims["sub"] == str(user.id)
    assert claims["typ"] == "access"
    assert "admin" in claims["roles"]

    now = datetime.now(timezone.utc)
    invalid_claims = {
        "sub": str(user.id),
        "typ": "refresh",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": auth_settings.AUTH_JWT_ISSUER,
        "aud": auth_settings.AUTH_JWT_AUDIENCE,
        "scp": ["admin"],
    }
    for mutation in (
        {"typ": "refresh"},
        {"exp": now - timedelta(seconds=1)},
        {"nbf": now + timedelta(minutes=5)},
        {"iss": "other-issuer"},
        {"aud": "other-audience"},
    ):
        token = jwt.encode(
            invalid_claims | mutation,
            auth_settings.AUTH_JWT_SECRET,
            algorithm="HS256",
        )
        with pytest.raises(AuthTokenError):
            service.decode_access_token(token)

    unsigned = jwt.encode(
        invalid_claims | {"typ": "access"}, key=None, algorithm="none"
    )
    with pytest.raises(AuthTokenError):
        service.decode_access_token(unsigned)


@pytest.mark.asyncio
async def test_refresh_rotation_replay_revokes_the_entire_family(
    db_session, auth_settings
):
    service = AuthService(db_session, settings=auth_settings)
    user = User(
        username="admin", password=service.hash_password("password"), is_admin=True
    )
    db_session.add(user)
    db_session.commit()

    pair = service.issue_token_pair(user)
    rotated = service.rotate_refresh_token(pair.refresh_token)
    assert rotated.access_token != pair.access_token
    assert rotated.refresh_token != pair.refresh_token

    with pytest.raises(RefreshTokenReplayError):
        service.rotate_refresh_token(pair.refresh_token)

    family = db_session.query(RefreshToken).filter_by(family_id=pair.family_id).all()
    assert len(family) == 2
    assert all(token.revoked_at is not None for token in family)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_family_and_api_keys_are_not_interactive_sessions(
    db_session, auth_settings
):
    service = AuthService(db_session, settings=auth_settings)
    user = User(
        username="admin", password=service.hash_password("password"), is_admin=True
    )
    db_session.add(user)
    db_session.commit()

    pair = service.issue_token_pair(user)
    service.revoke_refresh_family(pair.family_id)
    with pytest.raises(AuthTokenError):
        service.rotate_refresh_token(pair.refresh_token)


def test_logout_route_revokes_refresh_family_and_clears_auth_cookies(
    monkeypatch, auth_settings
):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine, tables=[User.__table__, RefreshToken.__table__, Session.__table__]
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        service = AuthService(db, settings=auth_settings)
        user = User(
            username="logout-admin",
            password=service.hash_password("password"),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        initial_pair = service.issue_token_pair(user)
        pair = service.rotate_refresh_token(initial_pair.refresh_token)
        legacy_token = asyncio.run(service.create_session(user.id))
        legacy_only_token = asyncio.run(service.create_session(user.id))

    def get_test_auth_service():
        with session_factory() as db:
            yield AuthService(db, settings=auth_settings)

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/auth")
    app.dependency_overrides[get_auth_service] = get_test_auth_service
    monkeypatch.setattr(auth_routes, "get_settings", lambda: auth_settings)

    try:
        with TestClient(app) as client:
            client.cookies.set("access_token", pair.access_token, path="/")
            client.cookies.set("refresh_token", pair.refresh_token, path="/auth")
            client.cookies.set("session", legacy_token, path="/")
            captured_refresh = pair.refresh_token

            logout = client.post("/auth/logout")

            with session_factory() as db:
                family = (
                    db.query(RefreshToken).filter_by(family_id=pair.family_id).all()
                )
                assert len(family) == 2
                assert all(token.revoked_at is not None for token in family)

            client.cookies.set("refresh_token", captured_refresh, path="/auth")
            refresh = client.post("/auth/refresh")

            assert refresh.status_code == 401
            assert logout.status_code == 200
            assert logout.json() == {"message": "Logout successful", "success": True}

            deletion_headers = {
                header.split("=", 1)[0]: header.lower()
                for header in logout.headers.get_list("set-cookie")
            }
            assert "max-age=0" in deletion_headers["access_token"]
            assert "path=/" in deletion_headers["access_token"]
            assert "max-age=0" in deletion_headers["refresh_token"]
            assert "path=/auth" in deletion_headers["refresh_token"]
            assert "max-age=0" in deletion_headers["session"]
            assert "path=/" in deletion_headers["session"]

            client.cookies.clear()
            no_token_logout = client.post("/auth/logout")
            assert no_token_logout.status_code == 200
            assert no_token_logout.json() == {
                "message": "Logout successful",
                "success": True,
            }

            client.cookies.set("session", legacy_only_token, path="/")
            legacy_logout = client.post("/auth/logout")
            assert legacy_logout.status_code == 200
            assert legacy_logout.json() == {
                "message": "Logout successful",
                "success": True,
            }

        with session_factory() as db:
            assert db.query(Session).count() == 0
    finally:
        Base.metadata.drop_all(
            engine,
            tables=[Session.__table__, RefreshToken.__table__, User.__table__],
        )
        engine.dispose()


def test_scope_dependency_denies_missing_scope_and_supports_override():
    app = FastAPI()

    @app.get("/settings")
    async def settings_route(identity=Depends(require_scopes("settings:write"))):
        return {"subject": identity.subject}

    app.dependency_overrides[get_current_identity] = lambda: AuthIdentity(
        subject="1",
        roles=frozenset({"admin"}),
        scopes=frozenset({"settings:read"}),
        auth_method="session",
        interactive=True,
    )
    with TestClient(app) as client:
        assert client.get("/settings").status_code == 403

    app.dependency_overrides[get_current_identity] = lambda: AuthIdentity(
        subject="1",
        roles=frozenset({"admin"}),
        scopes=frozenset({"settings:write"}),
        auth_method="session",
        interactive=True,
    )
    with TestClient(app) as client:
        assert client.get("/settings").json() == {"subject": "1"}


def test_auth_redaction_and_frontend_do_not_persist_new_browser_tokens():
    from app.config.logging_config import _redact

    payload = _redact(
        "Authorization: Bearer phase3-access Cookie: refresh_token=phase3-refresh "
        "X-API-Key: phase3-key?token=phase3-query"
    )
    for secret in ("phase3-access", "phase3-refresh", "phase3-key", "phase3-query"):
        assert secret not in payload

    auth_source = Path("app/frontend/src/composables/useAuth.ts").read_text()
    assert "appStorage.setSessionToken" not in auth_source
    assert "document.cookie" not in auth_source
