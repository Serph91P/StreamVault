import importlib.util
import logging
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text


MIGRATION_NAME = "041_encrypt_proxy_credentials_after_schema.py"
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / MIGRATION_NAME


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_041", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration_041.db'}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE global_settings ("
                "id INTEGER PRIMARY KEY, proxy_encryption_key VARCHAR(255))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE proxy_settings ("
                "id INTEGER PRIMARY KEY, proxy_url VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO global_settings (id, proxy_encryption_key) "
                "VALUES (1, NULL)"
            )
        )
    yield engine
    engine.dispose()


def _stored_key(engine):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT proxy_encryption_key FROM global_settings WHERE id = 1")
        ).scalar_one()


def _stored_proxy(engine):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT proxy_url FROM proxy_settings WHERE id = 1")
        ).scalar_one()


def _insert_proxy(engine, proxy_url):
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO proxy_settings (id, proxy_url) VALUES (1, :proxy_url)"),
            {"proxy_url": proxy_url},
        )


def test_migration_is_discovered_after_existing_schema_migrations():
    from app.services.system.migration_service import MigrationService

    scripts = [Path(path).name for path in MigrationService.get_all_migration_scripts()]

    assert MIGRATION_NAME in scripts
    assert scripts.index(MIGRATION_NAME) > scripts.index(
        "040_add_twitch_upstream_leases.py"
    )


def test_fresh_schema_without_proxies_generates_and_persists_valid_key(
    db_engine, monkeypatch
):
    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)

    _load_migration().upgrade(db_engine)

    key = _stored_key(db_engine)
    assert key is not None
    Fernet(key.encode("ascii"))


def test_plaintext_proxy_is_encrypted_with_persisted_key(db_engine, monkeypatch):
    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)
    plaintext_proxy = "https://" + "proxy.invalid:8443"
    _insert_proxy(db_engine, plaintext_proxy)

    _load_migration().upgrade(db_engine)

    key = _stored_key(db_engine)
    ciphertext = _stored_proxy(db_engine)
    assert ciphertext != plaintext_proxy
    assert (
        Fernet(key.encode("ascii")).decrypt(ciphertext.encode("ascii")).decode()
        == plaintext_proxy
    )


def test_existing_database_key_is_reused_exactly(db_engine, monkeypatch):
    database_key = Fernet.generate_key().decode("ascii")
    legacy_key = Fernet.generate_key().decode("ascii")
    with db_engine.begin() as connection:
        connection.execute(
            text("UPDATE global_settings SET proxy_encryption_key = :key WHERE id = 1"),
            {"key": database_key},
        )
    monkeypatch.setenv("PROXY_ENCRYPTION_KEY", legacy_key)

    _load_migration().upgrade(db_engine)

    assert _stored_key(db_engine) == database_key


def test_existing_database_key_in_later_row_populates_null_rows(db_engine, monkeypatch):
    database_key = Fernet.generate_key().decode("ascii")
    with db_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO global_settings (id, proxy_encryption_key) "
                "VALUES (2, :key)"
            ),
            {"key": database_key},
        )
    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)

    _load_migration().upgrade(db_engine)

    with db_engine.connect() as connection:
        stored_keys = (
            connection.execute(
                text("SELECT proxy_encryption_key FROM global_settings ORDER BY id")
            )
            .scalars()
            .all()
        )
    assert stored_keys == [database_key, database_key]


def test_valid_legacy_environment_key_is_persisted_and_used(db_engine, monkeypatch):
    legacy_key = Fernet.generate_key().decode("ascii")
    plaintext_proxy = "http://" + "legacy-proxy.invalid:8080"
    _insert_proxy(db_engine, plaintext_proxy)
    monkeypatch.setenv("PROXY_ENCRYPTION_KEY", legacy_key)

    _load_migration().upgrade(db_engine)

    assert _stored_key(db_engine) == legacy_key
    ciphertext = _stored_proxy(db_engine)
    assert (
        Fernet(legacy_key.encode("ascii")).decrypt(ciphertext.encode("ascii")).decode()
        == plaintext_proxy
    )


def test_existing_ciphertext_is_not_rewritten_on_repeat(db_engine, monkeypatch):
    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)
    plaintext_proxy = "http://" + "repeat-proxy.invalid:8080"
    _insert_proxy(db_engine, plaintext_proxy)
    migration = _load_migration()

    migration.upgrade(db_engine)
    first_ciphertext = _stored_proxy(db_engine)
    migration.upgrade(db_engine)

    assert _stored_proxy(db_engine) == first_ciphertext


def test_encrypted_proxy_without_recoverable_key_fails_closed(
    db_engine, monkeypatch, caplog, capsys
):
    lost_key = Fernet.generate_key()
    plaintext_proxy = "http://" + "unrecoverable.invalid:8080"
    ciphertext = Fernet(lost_key).encrypt(plaintext_proxy.encode()).decode("ascii")
    _insert_proxy(db_engine, ciphertext)
    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(SystemExit, match="recover proxy encryption key"):
        _load_migration().upgrade(db_engine)

    assert _stored_key(db_engine) is None
    assert _stored_proxy(db_engine) == ciphertext
    captured = capsys.readouterr()
    output = caplog.text + captured.out + captured.err
    for sensitive_value in (
        plaintext_proxy,
        ciphertext,
        lost_key.decode("ascii"),
    ):
        assert sensitive_value not in output


def test_output_does_not_expose_proxy_or_key(db_engine, monkeypatch, caplog, capsys):
    legacy_key = Fernet.generate_key().decode("ascii")
    username = "migration-user"
    inert_pieces = ("migration-", "pass", "word")
    password = "".join(inert_pieces)
    raw_proxy = "http://" + username + ":" + password + "@proxy.invalid:8080"
    _insert_proxy(db_engine, raw_proxy)
    monkeypatch.setenv("PROXY_ENCRYPTION_KEY", legacy_key)
    caplog.set_level(logging.DEBUG)

    _load_migration().upgrade(db_engine)

    captured = capsys.readouterr()
    output = caplog.text + captured.out + captured.err
    for sensitive_value in (raw_proxy, legacy_key, username, password):
        assert sensitive_value not in output
