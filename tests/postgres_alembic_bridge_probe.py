"""Destructive real-PostgreSQL acceptance probe for the Alembic bridge.

Run only against a disposable database whose name ends in ``_migration_test``::

    DATABASE_URL=postgresql+psycopg://.../streamvault_migration_test \
      .venv/bin/python tests/postgres_alembic_bridge_probe.py
"""

from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.database import database_lifecycle
from app.services.system.migration_service import MigrationService

DATABASE_URL = os.environ["DATABASE_URL"]
DATABASE_NAME = make_url(DATABASE_URL).database or ""
if not DATABASE_NAME.endswith("_migration_test"):
    raise RuntimeError("refusing destructive probe outside a *_migration_test database")


def _reset_database() -> None:
    with database_lifecycle.sync_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


def _schema_signature() -> tuple[tuple[str, tuple[str, ...]], ...]:
    inspector = inspect(database_lifecycle.sync_engine)
    ignored = {"alembic_version", "migrations", "p6_bridge_sentinel"}
    return tuple(
        (table, tuple(column["name"] for column in inspector.get_columns(table)))
        for table in sorted(set(inspector.get_table_names()) - ignored)
    )


def _assert_current() -> None:
    with database_lifecycle.sync_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == MigrationService.ALEMBIC_LEGACY_BASELINE
        )
        assert connection.execute(
            text("SELECT COUNT(*) FROM migrations WHERE success = TRUE")
        ).scalar_one() == len(MigrationService.LEGACY_MIGRATION_IDENTITIES)


def _run_single() -> None:
    assert MigrationService.run_migrations()
    _assert_current()


def _run_suite() -> None:
    _reset_database()

    # Fresh database, then current-database immediate restart.
    _run_single()
    with database_lifecycle.sync_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE p6_bridge_sentinel "
                "(id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO p6_bridge_sentinel VALUES (1, 'preserved')")
        )
    expected_schema = _schema_signature()
    _run_single()
    assert _schema_signature() == expected_schema

    # Representative pre-Alembic ledger with the historical `name` column.
    with database_lifecycle.sync_engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(
            text("ALTER TABLE migrations RENAME COLUMN script_name TO name")
        )
    _run_single()
    assert _schema_signature() == expected_schema

    # Interrupted bridge: DDL exists, but the final two ledger writes and stamp do not.
    with database_lifecycle.sync_engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(
            text(
                "DELETE FROM migrations WHERE script_name IN "
                "('044_twitch_auth_handoff_state.py', "
                "'20251110_add_streamer_banner.py')"
            )
        )
    _run_single()
    assert _schema_signature() == expected_schema
    with database_lifecycle.sync_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT value FROM p6_bridge_sentinel WHERE id = 1")
            ).scalar_one()
            == "preserved"
        )

    # Two first starts contend on the PostgreSQL advisory lock.
    database_lifecycle.dispose_sync()
    _reset_database()
    command = [sys.executable, __file__, "single"]
    first = subprocess.Popen(command, env=os.environ.copy())
    second = subprocess.Popen(command, env=os.environ.copy())
    assert first.wait() == 0
    assert second.wait() == 0
    _assert_current()
    _run_single()

    print(
        "PostgreSQL Alembic bridge: fresh/current/legacy/interrupted/"
        "concurrent/restart passed; schema identity and sentinel data preserved"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "single":
        _run_single()
    else:
        _run_suite()
