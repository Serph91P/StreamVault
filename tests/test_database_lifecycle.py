"""
Phase 2 persistence foundation: SQLAlchemy URL transformation and lifecycle.

These tests drive the lazy engine/sessionmaker lifecycle and the SQLAlchemy
URL-API based driver normalization (no string replacements so percent-encoded
credentials and query parameters survive).
"""

import pytest
from sqlalchemy.engine import make_url

from app.database import (
    Base,
    DatabaseLifecycle,
    get_async_db,
    to_async_url,
    to_sync_url,
)


def test_sqlite_async_url_transform():
    assert to_async_url("sqlite:///data/test.db") == "sqlite+aiosqlite:///data/test.db"
    assert to_async_url("sqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"


def test_postgres_async_url_uses_psycopg_driver():
    assert to_async_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert (
        to_async_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    )
    assert to_async_url("postgresql+psycopg2://u:p@h/db") == (
        "postgresql+psycopg://u:p@h/db"
    )


def test_percent_encoded_credentials_survive_async_transform():
    url = "postgresql://user:p%40ss%2Fword@host:5432/dbname"
    transformed = make_url(to_async_url(url))
    assert transformed.password == "p@ss/word"
    assert transformed.drivername == "postgresql+psycopg"


def test_query_parameters_survive_async_transform():
    url = "postgresql://u:p@h/db?sslmode=require&options=-c%20x%3Dy"
    transformed = make_url(to_async_url(url))
    assert transformed.query["sslmode"] == "require"
    assert transformed.query["options"] == "-c x=y"


def test_unsupported_async_scheme_raises():
    with pytest.raises(ValueError):
        to_async_url("mysql://u:p@h/db")


def test_sync_postgres_url_normalizes_to_psycopg():
    assert to_sync_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert to_sync_url("postgresql+psycopg://u:p@h/db") == (
        "postgresql+psycopg://u:p@h/db"
    )


def test_sync_sqlite_url_stays_sqlite():
    assert to_sync_url("sqlite:///data/test.db") == "sqlite:///data/test.db"


def test_lifecycle_is_lazy_no_engine_at_construction(monkeypatch):
    created_sync = []
    created_async = []

    import app.database as database

    real_create_engine = database.create_engine
    real_create_async_engine = database.create_async_engine

    def spy_create_engine(*args, **kwargs):
        created_sync.append(args[0])
        return real_create_engine(*args, **kwargs)

    def spy_create_async_engine(*args, **kwargs):
        created_async.append(args[0])
        return real_create_async_engine(*args, **kwargs)

    monkeypatch.setattr(database, "create_engine", spy_create_engine)
    monkeypatch.setattr(database, "create_async_engine", spy_create_async_engine)

    lifecycle = DatabaseLifecycle("sqlite:///:memory:")
    assert created_sync == []
    assert created_async == []

    lifecycle.sync_engine
    assert created_sync == ["sqlite:///:memory:"]
    assert created_async == []

    lifecycle.async_engine
    assert created_async == ["sqlite+aiosqlite:///:memory:"]

    # Session factories are lazy too.
    assert lifecycle._sync_session_factory is None
    lifecycle.sync_session_factory
    assert lifecycle._sync_session_factory is not None


def test_lifecycle_sync_configures_pool_pre_ping_for_postgres(monkeypatch):
    captured = {}

    import app.database as database

    real_create_engine = database.create_engine

    def spy_create_engine(*args, **kwargs):
        captured["url"] = args[0]
        captured["kwargs"] = kwargs
        return real_create_engine(*args, **kwargs)

    monkeypatch.setattr(database, "create_engine", spy_create_engine)

    lifecycle = DatabaseLifecycle("postgresql://u:p@h/db")
    lifecycle.sync_engine
    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_recycle"] == 1800


def test_lifecycle_sync_sqlite_uses_check_same_thread(monkeypatch):
    captured = {}

    import app.database as database

    real_create_engine = database.create_engine

    def spy_create_engine(*args, **kwargs):
        captured["kwargs"] = kwargs
        return real_create_engine(*args, **kwargs)

    monkeypatch.setattr(database, "create_engine", spy_create_engine)

    lifecycle = DatabaseLifecycle("sqlite:///tmp/test.db")
    lifecycle.sync_engine
    assert captured["kwargs"]["connect_args"] == {"check_same_thread": False}


def test_lifecycle_dispose_sync_releases_and_allows_recreation():
    lifecycle = DatabaseLifecycle("sqlite:///:memory:")
    first = lifecycle.sync_engine
    lifecycle.dispose_sync()
    second = lifecycle.sync_engine
    assert second is not first


@pytest.mark.asyncio
async def test_lifecycle_adispose_is_async_and_allows_recreation():
    lifecycle = DatabaseLifecycle("sqlite+aiosqlite:///:memory:")
    first = lifecycle.async_engine
    assert first is not None
    await lifecycle.adispose()
    second = lifecycle.async_engine
    assert second is not None
    await lifecycle.adispose()


@pytest.mark.asyncio
async def test_async_dependency_yields_a_session_without_committing(monkeypatch):
    lifecycle = DatabaseLifecycle("sqlite:///:memory:")
    monkeypatch.setattr("app.database.database_lifecycle", lifecycle)
    dependency = get_async_db()
    session = await anext(dependency)
    assert isinstance(session, type(lifecycle.async_session_factory()))
    await dependency.aclose()
    await lifecycle.adispose()


def test_metadata_has_stable_constraint_naming_conventions():
    naming = Base.metadata.naming_convention
    assert naming["pk"] == "pk_%(table_name)s"
    assert naming["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
