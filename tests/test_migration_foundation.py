"""
Phase 2 persistence foundation: migration orchestration on SQLite.

The migrations service must create its tracking table with SQLAlchemy
inspection (no PostgreSQL-only information_schema), stay idempotent, and
record only successful migrations (a failed migration must not produce a
success record).
"""

import importlib

import pytest
from sqlalchemy import create_engine, inspect, text

migration_service = importlib.import_module("app.services.system.migration_service")
MigrationService = migration_service.MigrationService


@pytest.fixture
def migration_engine(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'migrations.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(migration_service, "engine", engine)
    yield engine
    engine.dispose()


def _write_migration(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_ensure_migrations_table_creates_tracking_table(migration_engine):
    MigrationService.ensure_migrations_table()
    inspector = inspect(migration_engine)
    assert "migrations" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("migrations")}
    assert {"id", "script_name", "applied_at", "success"}.issubset(columns)


def test_ensure_migrations_table_is_idempotent(migration_engine):
    MigrationService.ensure_migrations_table()
    MigrationService.ensure_migrations_table()
    inspector = inspect(migration_engine)
    assert "migrations" in inspector.get_table_names()
    with migration_engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM migrations")).scalar()
    assert count == 0


def test_mark_migration_applied_upserts_single_success_row(migration_engine):
    MigrationService.ensure_migrations_table()
    assert MigrationService.is_migration_applied("001_example.py") is False

    MigrationService.mark_migration_applied("001_example.py")
    assert MigrationService.is_migration_applied("001_example.py") is True

    MigrationService.mark_migration_applied("001_example.py")
    with migration_engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM migrations WHERE script_name = '001_example.py'")
        ).scalar()
        success = connection.execute(
            text("SELECT success FROM migrations WHERE script_name = '001_example.py'")
        ).scalar()
    assert count == 1
    assert success
    assert MigrationService.get_applied_migrations() == ["001_example.py"]


def test_failed_migration_is_not_recorded(migration_engine, tmp_path):
    MigrationService.ensure_migrations_table()
    bad_script = _write_migration(
        tmp_path,
        "999_bad.py",
        "def upgrade():\n    raise RuntimeError('boom')\n",
    )
    success, message = MigrationService.run_migration_script(bad_script)
    assert success is False
    assert "boom" in message
    assert MigrationService.is_migration_applied("999_bad.py") is False
    assert MigrationService.get_applied_migrations() == []
    with migration_engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM migrations")).scalar()
    assert count == 0


def test_successful_migration_is_recorded(migration_engine, tmp_path):
    MigrationService.ensure_migrations_table()
    ok_script = _write_migration(
        tmp_path,
        "001_ok.py",
        "def upgrade():\n    return None\n",
    )
    success, message = MigrationService.run_migration_script(ok_script)
    assert success is True, message
    assert MigrationService.is_migration_applied("001_ok.py") is True
    assert MigrationService.get_applied_migrations() == ["001_ok.py"]


def test_pending_migrations_only_record_success_and_rerun_failed(
    migration_engine, tmp_path, monkeypatch
):
    MigrationService.ensure_migrations_table()
    ok_script = _write_migration(
        tmp_path,
        "001_ok.py",
        "def upgrade():\n    return None\n",
    )
    bad_script = _write_migration(
        tmp_path,
        "002_bad.py",
        "def upgrade():\n    raise RuntimeError('nope')\n",
    )
    monkeypatch.setattr(
        MigrationService,
        "get_all_migration_scripts",
        staticmethod(lambda: [ok_script, bad_script]),
    )

    results = MigrationService._run_pending_migrations()
    assert [result[0] for result in results] == ["001_ok.py", "002_bad.py"]
    assert results[0][1] is True
    assert results[1][1] is False

    assert MigrationService.get_applied_migrations() == ["001_ok.py"]
    with migration_engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM migrations")).scalar()
    assert count == 1

    # Already-applied migrations are skipped and the failed one stays pending.
    results_again = MigrationService._run_pending_migrations()
    assert [result[0] for result in results_again] == ["002_bad.py"]
    assert results_again[0][1] is False
    assert MigrationService.get_applied_migrations() == ["001_ok.py"]


def test_migration_invoker_uses_target_engine_for_compatible_scripts(
    migration_engine, tmp_path
):
    MigrationService.ensure_migrations_table()
    script = _write_migration(
        tmp_path,
        "003_target_engine.py",
        "from sqlalchemy import text\n"
        "def upgrade(target_engine=None):\n"
        "    assert target_engine is not None\n"
        "    with target_engine.begin() as c:\n"
        "        c.execute(text('CREATE TABLE target_engine_table (id INTEGER)'))\n",
    )
    success, message = MigrationService.run_migration_script(script)
    assert success is True, message
    inspector = inspect(migration_engine)
    assert "target_engine_table" in inspector.get_table_names()
