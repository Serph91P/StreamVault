"""Real PostgreSQL regressions for refresh-token single-use rotation."""

from __future__ import annotations

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import RefreshToken, User
from app.services.core.auth_service import (
    AuthService,
    RefreshTokenReplayError,
)


@pytest.fixture
def postgres_refresh_sessions():
    url = os.environ.get("STREAMVAULT_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("requires isolated STREAMVAULT_POSTGRES_TEST_URL")

    engine = create_engine(url, future=True, pool_pre_ping=True)
    Base.metadata.create_all(engine, tables=[User.__table__, RefreshToken.__table__])
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = SimpleNamespace(
        AUTH_JWT_SECRET="postgres-refresh-race-test-secret-long-enough-to-be-secure-123456",
        AUTH_JWT_ALGORITHM="HS256",
        AUTH_JWT_ISSUER="streamvault-test",
        AUTH_JWT_AUDIENCE="streamvault-test-api",
        AUTH_ACCESS_TOKEN_MINUTES=15,
        AUTH_REFRESH_TOKEN_HOURS=24,
        AUTH_REFRESH_FAMILY_MAX_HOURS=168,
    )
    try:
        yield SessionFactory, settings
    finally:
        Base.metadata.drop_all(engine, tables=[RefreshToken.__table__, User.__table__])
        engine.dispose()


def test_postgres_refresh_rotation_is_single_use_and_revokes_replayed_family(
    postgres_refresh_sessions,
) -> None:
    """Independent sessions must mint one child at most for a refresh token."""
    SessionFactory, settings = postgres_refresh_sessions
    with SessionFactory() as db:
        service = AuthService(db, settings=settings)
        user = User(
            username="postgres-refresh-race",
            password=service.hash_password("correct horse"),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        pair = service.issue_token_pair(user)

    contenders = 8
    barrier = threading.Barrier(contenders)

    def rotate_in_independent_session() -> tuple[str, str | None]:
        with SessionFactory() as db:
            service = AuthService(db, settings=settings)
            barrier.wait(timeout=10)
            try:
                rotated = service.rotate_refresh_token(pair.refresh_token)
                return "rotated", rotated.refresh_token
            except RefreshTokenReplayError:
                return "replayed", None

    with ThreadPoolExecutor(max_workers=contenders) as pool:
        results = list(
            pool.map(lambda _index: rotate_in_independent_session(), range(contenders))
        )

    assert [kind for kind, _token in results].count("rotated") == 1
    assert [kind for kind, _token in results].count("replayed") == contenders - 1

    with SessionFactory() as db:
        family = db.query(RefreshToken).filter_by(family_id=pair.family_id).all()

    assert len(family) == 2
    assert sum(token.parent_token_hash is None for token in family) == 1
    assert sum(token.parent_token_hash is not None for token in family) == 1
    assert all(token.revoked_at is not None for token in family)
    assert all(re.fullmatch(r"[0-9a-f]{64}", token.token_hash) for token in family)
    assert all(pair.refresh_token not in token.token_hash for token in family)


def test_postgres_refresh_rotation_rolls_back_a_failed_child_creation(
    postgres_refresh_sessions, monkeypatch
) -> None:
    """A child-insert failure must leave the original refresh token usable."""
    SessionFactory, settings = postgres_refresh_sessions
    with SessionFactory() as db:
        service = AuthService(db, settings=settings)
        user = User(
            username="postgres-refresh-rollback",
            password=service.hash_password("correct horse"),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        pair = service.issue_token_pair(user)

        with monkeypatch.context() as patch:
            patch.setattr(
                service,
                "_new_refresh_token",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("insert failed")
                ),
            )
            with pytest.raises(RuntimeError, match="insert failed"):
                service.rotate_refresh_token(pair.refresh_token)

        db.expire_all()

    with SessionFactory() as db:
        original = db.query(RefreshToken).filter_by(family_id=pair.family_id).one()
        assert original.used_at is None
        assert original.revoked_at is None
        rotated = AuthService(db, settings=settings).rotate_refresh_token(
            pair.refresh_token
        )
        assert rotated.refresh_token != pair.refresh_token
