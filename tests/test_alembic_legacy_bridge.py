"""Lossless transition from the numbered migration ledger to Alembic."""

import ast
import importlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

migration_service = importlib.import_module("app.services.system.migration_service")
MigrationService = migration_service.MigrationService


def test_supported_legacy_identity_inventory_matches_shipped_scripts():
    discovered = tuple(
        path.name
        for path in sorted(
            [
                *Path("migrations").glob("[0-9][0-9][0-9]_*.py"),
                *Path("migrations").glob("20[0-9][0-9]*_*.py"),
            ]
        )
    )

    assert MigrationService.LEGACY_MIGRATION_IDENTITIES == discovered
    assert len(discovered) == len(set(discovered)) == 48

    aliases = tuple(
        path.name
        for path in sorted(Path("migrations/old_migrations_backup").glob("*.py"))
    )
    assert MigrationService.SUPPORTED_LEGACY_ALIASES == aliases
    assert len(aliases) == len(set(aliases)) == 15


def test_historical_migrations_do_not_import_current_orm_models():
    offenders = []
    paths = [
        Path("migrations") / name
        for name in MigrationService.LEGACY_MIGRATION_IDENTITIES
    ]
    paths.extend(
        Path("migrations/old_migrations_backup") / name
        for name in MigrationService.SUPPORTED_LEGACY_ALIASES
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "app.models" or node.module.startswith("app.models."):
                    offenders.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app.models" or alias.name.startswith(
                        "app.models."
                    ):
                        offenders.append(f"{path}:{node.lineno}")

    assert offenders == []


@pytest.fixture
def bridge_engine(tmp_path, monkeypatch):
    target = create_engine(f"sqlite:///{tmp_path / 'bridge.db'}", future=True)
    monkeypatch.setattr(migration_service, "engine", target)
    yield target
    target.dispose()


def _record_complete_legacy_history(target):
    MigrationService.ensure_migrations_table()
    with target.begin() as connection:
        for identity in MigrationService.LEGACY_MIGRATION_IDENTITIES:
            connection.execute(
                text(
                    "INSERT INTO migrations (script_name, success) "
                    "VALUES (:identity, TRUE)"
                ),
                {"identity": identity},
            )


def test_bridge_stamps_complete_legacy_history_without_touching_application_data(
    bridge_engine,
):
    with bridge_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE sentinel (id INTEGER PRIMARY KEY, value VARCHAR NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO sentinel VALUES (7, 'preserved')"))
    _record_complete_legacy_history(bridge_engine)

    MigrationService._bridge_legacy_history_to_alembic()

    with bridge_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT value FROM sentinel WHERE id = 7")
            ).scalar_one()
            == "preserved"
        )
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == MigrationService.ALEMBIC_LEGACY_BASELINE
        )

    # Immediate restart is a no-op and preserves both identity and data.
    MigrationService._bridge_legacy_history_to_alembic()
    with bridge_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM alembic_version")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT value FROM sentinel WHERE id = 7")
            ).scalar_one()
            == "preserved"
        )


def test_bridge_rejects_interrupted_legacy_history_without_stamping(bridge_engine):
    MigrationService.ensure_migrations_table()
    with bridge_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO migrations (script_name, success) VALUES (:identity, TRUE)"
            ),
            {"identity": MigrationService.LEGACY_MIGRATION_IDENTITIES[0]},
        )

    with pytest.raises(RuntimeError, match="legacy migration history is incomplete"):
        MigrationService._bridge_legacy_history_to_alembic()

    with bridge_engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
    assert "alembic_version" not in tables


def test_unknown_successful_legacy_identity_is_rejected(bridge_engine):
    _record_complete_legacy_history(bridge_engine)
    with bridge_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO migrations (script_name, success) VALUES ('999_unknown.py', TRUE)"
            )
        )

    with pytest.raises(RuntimeError, match="unsupported legacy migration identities"):
        MigrationService._bridge_legacy_history_to_alembic()


def test_documented_historical_alias_is_accepted(bridge_engine):
    _record_complete_legacy_history(bridge_engine)
    with bridge_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO migrations (script_name, success) VALUES (:identity, TRUE)"
            ),
            {"identity": MigrationService.SUPPORTED_LEGACY_ALIASES[0]},
        )

    MigrationService._bridge_legacy_history_to_alembic()
    with bridge_engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision == MigrationService.ALEMBIC_LEGACY_BASELINE
