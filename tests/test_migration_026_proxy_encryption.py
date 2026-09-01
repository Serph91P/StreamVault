import importlib.util
import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "026_encrypt_proxy_credentials.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_026", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_defers_encryption_before_proxy_key_schema(
    tmp_path, monkeypatch, caplog
):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration_026.db'}", future=True)
    Session = sessionmaker(bind=engine, future=True)
    plaintext_proxy = "http://" + "proxy.invalid:8080"

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE global_settings ("
                "id INTEGER PRIMARY KEY, notifications_enabled BOOLEAN)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO global_settings (id, notifications_enabled) "
                "VALUES (1, true)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE proxy_settings ("
                "id INTEGER PRIMARY KEY, proxy_url VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO proxy_settings (id, proxy_url) VALUES (1, :proxy_url)"),
            {"proxy_url": plaintext_proxy},
        )

    migration = _load_migration()
    monkeypatch.setattr(migration, "SessionLocal", Session, raising=False)
    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)

    from app.utils import proxy_encryption

    monkeypatch.setattr(proxy_encryption, "_proxy_encryption", None)
    caplog.set_level(logging.ERROR)

    migration.upgrade()
    migration.upgrade()

    with engine.connect() as connection:
        stored_proxy = connection.execute(
            text("SELECT proxy_url FROM proxy_settings WHERE id = 1")
        ).scalar_one()

    assert stored_proxy == plaintext_proxy
    assert not any(
        marker in caplog.text for marker in ("ERROR", "CRITICAL", "Traceback")
    )
    engine.dispose()


def test_upgrade_completes_cleanly_with_no_proxy_rows(tmp_path, caplog):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration_026_empty.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE proxy_settings ("
                "id INTEGER PRIMARY KEY, proxy_url VARCHAR NOT NULL)"
            )
        )
    caplog.set_level(logging.ERROR)

    migration = _load_migration()
    migration.upgrade()
    migration.upgrade()

    assert not caplog.records
    engine.dispose()
