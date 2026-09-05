"""
SQLAlchemy 2.x lifecycle and compatibility seam for StreamVault.

The ``DatabaseLifecycle`` owns lazy sync + async engines and sessionmakers.
Nothing here creates an engine (or opens a connection) at import time; the
first access to ``sync_engine`` / ``async_engine`` / session factories builds
them on demand, and ``dispose_sync()`` / ``adispose()`` release them.

Driver normalization happens through the SQLAlchemy URL APIs (``make_url`` +
``set(drivername=...)``) so percent-encoded credentials and query parameters
survive; there is deliberately no ``.replace()``-style URL rewriting.

Compatibility seam (temporary):
    ``Base``, ``get_db``, ``SessionLocal`` and ``engine`` are preserved as
    documented temporary compatibility exports so the large body of sync call
    sites keeps working unchanged. New code should depend on
    ``database_lifecycle`` and the async repositories instead.
"""

import logging
import os
import sys
from typing import AsyncGenerator, Dict, Optional

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Get DATABASE_URL from environment (used as a fallback during early
# initialization; settings remain authoritative).
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///:memory:"

logger = logging.getLogger("streamvault")

is_testing = "pytest" in sys.modules or "import_test.py" in sys.argv[0]

_SYNC_DRIVERNAMES: Dict[str, str] = {
    "postgresql": "postgresql+psycopg",
    "postgresql+psycopg": "postgresql+psycopg",
    "postgresql+psycopg2": "postgresql+psycopg",
    "sqlite": "sqlite",
    "sqlite+aiosqlite": "sqlite",
}

_ASYNC_DRIVERNAMES: Dict[str, str] = {
    "postgresql": "postgresql+psycopg",
    "postgresql+psycopg": "postgresql+psycopg",
    "postgresql+psycopg2": "postgresql+psycopg",
    "sqlite": "sqlite+aiosqlite",
    "sqlite+aiosqlite": "sqlite+aiosqlite",
}


def to_sync_url(database_url: str) -> str:
    """Normalize a URL for the sync engine via the SQLAlchemy URL API.

    The drivername is swapped (e.g. ``postgresql`` -> ``postgresql+psycopg``)
    while the password and query parameters stay untouched.
    """
    return _transform_driver(database_url, _SYNC_DRIVERNAMES)


def to_async_url(database_url: str) -> str:
    """Map a URL to its async driver equivalent.

    ``sqlite`` becomes ``sqlite+aiosqlite`` and the postgres family becomes
    ``postgresql+psycopg`` for the async engine. Credentials and query
    parameters survive because only the drivername is changed.
    """
    return _transform_driver(database_url, _ASYNC_DRIVERNAMES)


def _transform_driver(database_url: str, drivername_map: Dict[str, str]) -> str:
    url = make_url(database_url)
    try:
        target = drivername_map[url.drivername]
    except KeyError:
        raise ValueError(f"Unsupported database scheme: {url.drivername!r}") from None
    return url.set(drivername=target).render_as_string(hide_password=False)


def _is_in_memory_sqlite(url: URL) -> bool:
    return url.drivername.startswith("sqlite") and url.database in (None, ":memory:")


class DatabaseLifecycle:
    """Lazily own the sync + async engines and their session factories."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._configured_url = database_url
        self._resolved_url: Optional[str] = None
        self._sync_engine: Optional[Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_session_factory = None
        self._async_session_factory = None

    @property
    def url(self) -> str:
        if self._resolved_url is None:
            self._resolved_url = (
                self._configured_url
                if self._configured_url is not None
                else get_database_url()
            )
        return self._resolved_url

    @property
    def sync_url(self) -> str:
        return to_sync_url(self.url)

    @property
    def async_url(self) -> str:
        return to_async_url(self.url)

    @property
    def sync_engine(self) -> Engine:
        if self._sync_engine is None:
            engine_url = make_url(self.sync_url)
            if engine_url.drivername.startswith("sqlite"):
                kwargs = {"connect_args": {"check_same_thread": False}}
                if _is_in_memory_sqlite(engine_url):
                    kwargs["poolclass"] = StaticPool
            else:
                kwargs = {
                    "pool_pre_ping": True,
                    "pool_recycle": 1800,
                    "pool_size": 20,
                    "max_overflow": 50,
                    "pool_timeout": 15,
                    "connect_args": {
                        "connect_timeout": 5,
                        "application_name": "StreamVault",
                    },
                }
            self._sync_engine = create_engine(self.sync_url, future=True, **kwargs)
        return self._sync_engine

    @property
    def async_engine(self) -> AsyncEngine:
        if self._async_engine is None:
            engine_url = make_url(self.async_url)
            if engine_url.drivername.startswith("sqlite"):
                kwargs = {}
                if _is_in_memory_sqlite(engine_url):
                    kwargs["poolclass"] = StaticPool
            else:
                kwargs = {
                    "pool_pre_ping": True,
                    "pool_recycle": 1800,
                    "pool_size": 20,
                    "max_overflow": 50,
                    "pool_timeout": 15,
                }
            self._async_engine = create_async_engine(
                self.async_url, echo=False, **kwargs
            )
        return self._async_engine

    @property
    def sync_session_factory(self):
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                bind=self.sync_engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        return self._sync_session_factory

    @property
    def async_session_factory(self):
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_factory

    def dispose_sync(self) -> None:
        """Synchronously dispose any created engines (safe for both backends)."""
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
        if self._async_engine is not None:
            self._async_engine.sync_engine.dispose()
            self._async_engine = None
        self._sync_session_factory = None
        self._async_session_factory = None

    async def adispose(self) -> None:
        """Await async engine disposal and synchronously dispose the sync engine."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
        self._sync_session_factory = None
        self._async_session_factory = None


class _EngineProxy:
    """Temporary compatibility seam: ``from app.database import engine``.

    Attribute access is forwarded to the lifecycle's lazily-created sync
    engine; ``dispose`` releases both engines through the lifecycle.
    """

    def __init__(self, lifecycle: DatabaseLifecycle) -> None:
        self._lifecycle = lifecycle

    def __getattr__(self, item: str):
        if item == "dispose":
            return self._lifecycle.dispose_sync
        return getattr(self._lifecycle.sync_engine, item)


class _SessionLocalProxy:
    """Temporary compatibility seam: ``SessionLocal()`` creates sessions.

    All calls are forwarded to the lifecycle's lazily-created sync
    sessionmaker so no sessionmaker is built at import time.
    """

    def __init__(self, lifecycle: DatabaseLifecycle) -> None:
        self._lifecycle = lifecycle

    def __call__(self, *args, **kwargs):
        return self._lifecycle.sync_session_factory(*args, **kwargs)

    def __getattr__(self, item: str):
        return getattr(self._lifecycle.sync_session_factory, item)


def get_database_url() -> str:
    """
    Resolve the validated database URL for connections.

    Settings are authoritative; the environment variable is used as a
    fallback and in-memory SQLite is used in testing.
    """
    try:
        from app.config.settings import settings

        url = settings.DATABASE_URL
        if not url:
            url = DATABASE_URL
    except ImportError:
        url = DATABASE_URL

    if not url:
        raise ValueError("DATABASE_URL is not set.")

    if is_testing:
        return "sqlite:///:memory:"

    return url


def get_db():
    """FastAPI dependency yielding a sync session from the lifecycle.

    Temporary compatibility seam; new dependencies should prefer the async
    repositories or explicitly request ``database_lifecycle``.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session without implicitly committing its work."""
    async with database_lifecycle.async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Process-scoped lifecycle. No engine is created at import time.
database_lifecycle = DatabaseLifecycle()

Base = declarative_base(
    metadata=MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
)

# ---------------------------------------------------------------------------
# Temporary compatibility exports (documented seam above).
# ---------------------------------------------------------------------------
engine = _EngineProxy(database_lifecycle)
SessionLocal = _SessionLocalProxy(database_lifecycle)
