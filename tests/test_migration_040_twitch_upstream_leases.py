import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

MIGRATION_NAME = "040_add_twitch_upstream_leases.py"
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / MIGRATION_NAME


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_040", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_repeat_downgrade_and_reupgrade(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'migration_040.db'}", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE recordings (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text("CREATE TABLE global_settings (id INTEGER PRIMARY KEY)")
        )

    migration = _load_migration()
    migration.upgrade(engine)
    migration.upgrade(engine)

    inspector = inspect(engine)
    assert "twitch_upstream_leases" in inspector.get_table_names()
    assert "twitch_upstream_coordination_state" in inspector.get_table_names()
    assert "twitch_max_concurrent_upstreams" in {
        column["name"] for column in inspector.get_columns("global_settings")
    }
    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("twitch_upstream_leases")
    }
    assert set(indexes) == {
        "ix_twitch_upstream_leases_state_expiry",
        "ix_twitch_upstream_leases_auth_state",
        "ix_twitch_upstream_leases_owner_state",
        "ix_twitch_upstream_leases_recording_id",
        "uq_twitch_upstream_leases_channel_key",
    }
    assert indexes["uq_twitch_upstream_leases_channel_key"]["unique"]
    with engine.connect() as connection:
        guard = connection.execute(
            text("SELECT id, lock_version FROM twitch_upstream_coordination_state")
        ).one()
        assert guard == (1, 0)

    migration.downgrade(engine)
    assert "twitch_upstream_leases" not in inspect(engine).get_table_names()
    assert "twitch_upstream_coordination_state" not in inspect(engine).get_table_names()

    migration.upgrade(engine)
    assert "twitch_upstream_leases" in inspect(engine).get_table_names()
    engine.dispose()


def test_migration_is_discovered() -> None:
    from app.services.system.migration_service import MigrationService

    scripts = [Path(path).name for path in MigrationService.get_all_migration_scripts()]
    assert MIGRATION_NAME in scripts
    assert hasattr(_load_migration(), "upgrade")


@pytest.mark.parametrize("state", ["STARTING", "ACTIVE", "ROTATING", "RECOVERING"])
def test_downgrade_refuses_active_lease_without_changing_schema_or_data(
    tmp_path, state
) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / f'migration_040_{state.lower()}.db'}", future=True
    )
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE recordings (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text("CREATE TABLE global_settings (id INTEGER PRIMARY KEY)")
        )

    migration = _load_migration()
    migration.upgrade(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO twitch_upstream_leases "
                "(channel_key, purpose, state, generation, reserved_at, heartbeat_at, "
                "expires_at, created_at, updated_at) VALUES "
                "(:channel_key, 'RECORDING', :state, 1, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"channel_key": f"channel-{state.lower()}", "state": state},
        )

    with pytest.raises(RuntimeError, match="active Twitch upstream leases"):
        migration.downgrade(engine)

    assert {
        "twitch_upstream_leases",
        "twitch_upstream_coordination_state",
    }.issubset(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT channel_key, state FROM twitch_upstream_leases")
        ).one() == (f"channel-{state.lower()}", state)

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE twitch_upstream_leases SET state = 'RELEASED', "
                "released_at = CURRENT_TIMESTAMP"
            )
        )
    migration.downgrade(engine)
    assert "twitch_upstream_leases" not in inspect(engine).get_table_names()
    assert "twitch_upstream_coordination_state" not in inspect(engine).get_table_names()
    engine.dispose()
