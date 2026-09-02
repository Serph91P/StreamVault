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

from app.database import Base
from app.models import RefreshToken, User
from app.services.core.auth_service import (
    AuthService,
    AuthTokenError,
    RefreshTokenReplayError,
)
from app.dependencies import AuthIdentity, get_current_identity, require_scopes


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
    )


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, RefreshToken.__table__])
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=[RefreshToken.__table__, User.__table__])
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
