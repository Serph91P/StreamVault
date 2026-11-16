"""Migration orchestration must stay on its explicitly supplied database."""

from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.services.system.migration_service import MigrationService


def test_legacy_dialect_uses_supplied_engine_without_global_url(
    tmp_path: Path, monkeypatch
) -> None:
    import importlib.util
    from sqlalchemy import text

    path = (
        Path(__file__).resolve().parents[1]
        / "migrations/016_add_use_global_cleanup_policy.py"
    )
    spec = importlib.util.spec_from_file_location("scoped_legacy_016", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(
        migration,
        "settings",
        migration.settings.model_copy(update={"database_url": None}),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'dialect.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE streamer_recording_settings (id INTEGER PRIMARY KEY)"
                )
            )
            connection.execute(
                text("INSERT INTO streamer_recording_settings (id) VALUES (1)")
            )
        assert migration.run_migration(target_engine=engine) is True
        column = next(
            c
            for c in inspect(engine).get_columns("streamer_recording_settings")
            if c["name"] == "use_global_cleanup_policy"
        )
        assert str(column["type"]) == "INTEGER"
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT use_global_cleanup_policy FROM streamer_recording_settings"
                    )
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_migration_session_keeps_explicit_engine_and_legacy_fallback(
    tmp_path: Path,
) -> None:
    from sqlalchemy.orm import Session
    from app.services.system.migration_service import migration_session

    explicit = create_engine(f"sqlite:///{tmp_path / 'explicit.db'}")
    legacy = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    fallback_calls = []

    def fallback() -> Session:
        fallback_calls.append(True)
        return Session(bind=legacy)

    try:
        with migration_session(explicit, fallback) as session:
            assert session.get_bind() is explicit
            assert session.autoflush is False
            assert session.expire_on_commit is False
        assert fallback_calls == []
        with migration_session(None, fallback) as session:
            assert session.get_bind() is legacy
        assert fallback_calls == [True]
    finally:
        explicit.dispose()
        legacy.dispose()


def test_bound_migration_ledgers_and_scripts_do_not_cross_engines(
    tmp_path: Path,
) -> None:
    engines = [
        create_engine(f"sqlite:///{tmp_path / f'{name}.db'}")
        for name in ("first", "second")
    ]
    script = tmp_path / "001_scoped.py"
    script.write_text(
        "from sqlalchemy import text\ndef upgrade(target_engine):\n    with target_engine.begin() as connection:\n        connection.execute(text('CREATE TABLE scoped_effect (id INTEGER)'))\n"
    )
    try:
        first, second = [MigrationService.for_engine(engine) for engine in engines]
        first.ensure_migrations_table()
        second.ensure_migrations_table()
        assert first.run_migration_script(str(script))[0] is True
        assert first.is_migration_applied(script.name) is True
        assert second.is_migration_applied(script.name) is False
        assert inspect(engines[0]).has_table("scoped_effect")
        assert not inspect(engines[1]).has_table("scoped_effect")
        assert second.run_migration_script(str(script))[0] is True
        assert inspect(engines[1]).has_table("scoped_effect")
        assert (
            first.get_applied_migrations()
            == second.get_applied_migrations()
            == [script.name]
        )
    finally:
        for engine in engines:
            engine.dispose()
