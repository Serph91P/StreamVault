"""Run only against two empty, explicitly supplied disposable PostgreSQL DBs."""

import os
import argparse
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from app.database import database_lifecycle
from app.services.system.migration_service import MigrationService


def schema_signature(engine: Engine) -> dict[str, object]:
    inspector = inspect(engine)
    return {
        name: {
            "columns": [
                (c["name"], str(c["type"]), c["nullable"], c["default"])
                for c in inspector.get_columns(name)
            ],
            "primary_key": inspector.get_pk_constraint(name),
            "foreign_keys": sorted(inspector.get_foreign_keys(name), key=repr),
            "indexes": sorted(inspector.get_indexes(name), key=repr),
            "unique_constraints": sorted(
                inspector.get_unique_constraints(name), key=repr
            ),
        }
        for name in sorted(inspector.get_table_names())
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    target = create_engine(os.environ["SCOPED_MIGRATION_TEST_URL"])
    default = database_lifecycle.sync_engine
    try:
        assert (
            target.url.get_backend_name()
            == default.url.get_backend_name()
            == "postgresql"
        )
        assert target.url != default.url
        assert not inspect(target).get_table_names(), "target must be empty"
        assert not inspect(default).get_table_names(), "default must be empty"
        scoped = MigrationService.for_engine(target)
        scoped.ensure_migrations_table()
        path = (
            Path(__file__).resolve().parents[1] / "migrations/001_create_base_tables.py"
        )
        assert scoped.run_migration_script(str(path))[0] is True
        assert inspect(target).has_table("users"), (
            "legacy migration missed its injected database"
        )
        assert not inspect(default).get_table_names(), (
            "legacy migration mutated the default database"
        )
        assert scoped.get_applied_migrations() == [path.name]
        print(
            "PASS: actual legacy001 schema and ledger confined to injected PostgreSQL database"
        )
        if args.all:
            assert scoped.run_migrations() is True, (
                "scoped legacy/Alembic startup failed"
            )
            assert set(scoped.get_applied_migrations()) == set(
                scoped.LEGACY_MIGRATION_IDENTITIES
            )
            assert inspect(target).has_table("twitch_upstream_leases")
            assert not inspect(default).get_table_names(), (
                "migration sequence mutated default database"
            )
            print(
                "PASS: complete legacy/Alembic sequence confined to injected database"
            )
            assert MigrationService.run_migrations() is True
            assert set(MigrationService.get_applied_migrations()) == set(
                scoped.LEGACY_MIGRATION_IDENTITIES
            )
            assert schema_signature(default) == schema_signature(target)
            print(
                "PASS: default compatibility sequence has identical reflected schema and identities"
            )
    finally:
        target.dispose()
        database_lifecycle.dispose_sync()


if __name__ == "__main__":
    main()
