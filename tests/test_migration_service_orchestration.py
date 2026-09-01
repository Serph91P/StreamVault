import importlib
from types import SimpleNamespace

import pytest

migration_service = importlib.import_module("app.services.system.migration_service")


class _LockConnection:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("connection_opened")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.events.append("connection_closed")

    def execute(self, statement, parameters):
        sql = str(statement)
        assert parameters == {
            "lock_id": migration_service.MigrationService._POSTGRES_MIGRATION_LOCK_ID
        }
        if "pg_advisory_lock" in sql:
            self.events.append("lock_acquired")
        elif "pg_advisory_unlock" in sql:
            self.events.append("lock_released")
        else:
            raise AssertionError(f"Unexpected lock connection SQL: {sql}")


class _Engine:
    def __init__(self, dialect_name, events):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.events = events

    def connect(self):
        if self.dialect.name != "postgresql":
            raise AssertionError("SQLite must not open a migration lock connection")
        return _LockConnection(self.events)


def test_postgres_lock_wraps_initialization_discovery_and_execution(monkeypatch):
    events = []
    monkeypatch.setattr(migration_service, "engine", _Engine("postgresql", events))
    monkeypatch.setattr(
        migration_service.MigrationService,
        "ensure_migrations_table",
        staticmethod(lambda: events.append("migrations_table_initialized")),
    )

    def run_pending(cls):
        events.append("applied_migrations_read")
        events.append("migrations_executed_and_recorded")
        return [("001_example.py", True, "ok")]

    monkeypatch.setattr(
        migration_service.MigrationService,
        "_run_pending_migrations",
        classmethod(run_pending),
    )

    assert migration_service.MigrationService.run_migrations() is True
    assert events == [
        "connection_opened",
        "lock_acquired",
        "migrations_table_initialized",
        "applied_migrations_read",
        "migrations_executed_and_recorded",
        "lock_released",
        "connection_closed",
    ]


def test_postgres_lock_releases_when_migration_orchestration_raises(monkeypatch):
    events = []
    monkeypatch.setattr(migration_service, "engine", _Engine("postgresql", events))

    def fail_initialization():
        events.append("migrations_table_failed")
        raise RuntimeError("migration initialization failed")

    monkeypatch.setattr(
        migration_service.MigrationService,
        "ensure_migrations_table",
        staticmethod(fail_initialization),
    )

    with pytest.raises(RuntimeError, match="migration initialization failed"):
        migration_service.MigrationService.run_migrations()

    assert events == [
        "connection_opened",
        "lock_acquired",
        "migrations_table_failed",
        "lock_released",
        "connection_closed",
    ]


def test_sqlite_migration_orchestration_remains_unlocked(monkeypatch):
    events = []
    monkeypatch.setattr(migration_service, "engine", _Engine("sqlite", events))
    monkeypatch.setattr(
        migration_service.MigrationService,
        "ensure_migrations_table",
        staticmethod(lambda: events.append("migrations_table_initialized")),
    )

    def run_pending(cls):
        events.append("migrations_executed")
        return []

    monkeypatch.setattr(
        migration_service.MigrationService,
        "_run_pending_migrations",
        classmethod(run_pending),
    )

    assert migration_service.MigrationService.run_migrations() is True
    assert events == ["migrations_table_initialized", "migrations_executed"]
