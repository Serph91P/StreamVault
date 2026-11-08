"""Empty and legacy SQLite databases reach the catalog revision losslessly."""

import importlib

from sqlalchemy import create_engine, inspect, text
from alembic import command
from app.database import Base
from app import models  # noqa: F401


def test_catalog_migration_empty_database_and_restart_preserve_rows(
    monkeypatch, tmp_path
):
    module = importlib.import_module("app.services.system.migration_service")
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    monkeypatch.setattr(module, "engine", engine)
    try:
        # Historical numbered migrations are PostgreSQL-only. Exercise the new
        # canonical revision from the prior stamped SQLite schema, not those scripts.
        Base.metadata.create_all(
            engine,
            tables=[
                table
                for table in Base.metadata.sorted_tables
                if table.name not in {"video_catalog_entries", "background_tasks", "background_task_dependencies"}
            ],
        )
        with engine.begin() as connection:
            command.stamp(
                module.MigrationService._alembic_config(connection), "20260922_legacy"
            )
        assert module.MigrationService.run_migrations()
        assert "video_catalog_entries" in inspect(engine).get_table_names()
        with engine.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "20261106_tasks"
            )
            connection.execute(
                text(
                    "CREATE TABLE preserved_sentinel (id INTEGER PRIMARY KEY, value TEXT)"
                )
            )
            connection.execute(
                text("INSERT INTO preserved_sentinel VALUES (1, 'unchanged')")
            )
        assert module.MigrationService.run_migrations()
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT value FROM preserved_sentinel")
                ).scalar_one()
                == "unchanged"
            )
    finally:
        engine.dispose()
