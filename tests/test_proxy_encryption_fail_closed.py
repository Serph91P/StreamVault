"""Persistent proxy identity failures must never yield a new ephemeral cipher."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import event

from app import database as database_module
from app.database import Base, DatabaseLifecycle
from app.models import GlobalSettings
from app.utils.proxy_encryption import ProxyEncryption


def test_real_cipher_rejects_wrong_identity_and_invalid_utf8_without_fallback():
    from cryptography.fernet import InvalidToken

    first = ProxyEncryption(Fernet.generate_key().decode())
    second = ProxyEncryption(Fernet.generate_key().decode())
    encrypted = first.encrypt("http://synthetic.invalid:8080")
    with pytest.raises(InvalidToken):
        second.decrypt(encrypted)
    with pytest.raises(UnicodeEncodeError):
        first.encrypt("http://synthetic.invalid/\ud800")
    assert first.decrypt(encrypted) == "http://synthetic.invalid:8080"
    assert first.encrypt("") == first.decrypt("") == ""


def test_invalid_explicit_environment_identity_fails_without_generation(monkeypatch):
    def unavailable():
        raise RuntimeError("synthetic proxy identity database outage")

    def forbidden():
        raise AssertionError("invalid configured identity was replaced")

    monkeypatch.setenv("PROXY_ENCRYPTION_KEY", "synthetic-invalid-key")
    monkeypatch.setattr(database_module, "SessionLocal", unavailable)
    monkeypatch.setattr(Fernet, "generate_key", forbidden)
    with pytest.raises(ValueError):
        ProxyEncryption()


def test_unavailable_proxy_identity_never_generates_ephemeral_key(monkeypatch):
    generated = []
    native = Fernet.generate_key

    def generate():
        generated.append(True)
        return native()

    def unavailable():
        raise RuntimeError("synthetic proxy identity database outage")

    monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(database_module, "SessionLocal", unavailable)
    monkeypatch.setattr(Fernet, "generate_key", generate)
    with pytest.raises(RuntimeError, match="Persistent proxy identity unavailable"):
        ProxyEncryption()
    assert not generated


@pytest.mark.asyncio
async def test_failed_proxy_identity_commit_does_not_escape_with_ephemeral_cipher(
    tmp_path, monkeypatch
):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'identity.db'}")
    generated = []
    native = Fernet.generate_key

    def generate():
        generated.append(True)
        return native()

    def unavailable(_connection, _cursor, statement, *_):
        if statement.lstrip().startswith("UPDATE global_settings"):
            raise RuntimeError("synthetic proxy identity commit failure")

    try:
        with lifecycle.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(GlobalSettings())
            session.commit()
        monkeypatch.delenv("PROXY_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(
            database_module, "SessionLocal", lifecycle.sync_session_factory
        )
        monkeypatch.setattr(Fernet, "generate_key", generate)
        event.listen(lifecycle.sync_engine, "before_cursor_execute", unavailable)
        try:
            with pytest.raises(
                RuntimeError, match="Persistent proxy identity unavailable"
            ):
                ProxyEncryption()
        finally:
            event.remove(lifecycle.sync_engine, "before_cursor_execute", unavailable)
        assert len(generated) == 1
        assert (
            "streamvault.proxy_encryption"
            not in lifecycle.sync_session_factory.kw.get("info", {})
        )
        with lifecycle.sync_session_factory() as session:
            assert session.query(GlobalSettings).one().proxy_encryption_key is None
        assert lifecycle.sync_engine.pool.checkedout() == 0
    finally:
        await lifecycle.adispose()


def test_explicit_legacy_environment_identity_stays_usable_without_rotation(
    monkeypatch,
):
    key = Fernet.generate_key().decode()

    def unavailable():
        raise RuntimeError("synthetic proxy identity database outage")

    def forbidden():
        raise AssertionError("explicit existing environment identity was rotated")

    monkeypatch.setenv("PROXY_ENCRYPTION_KEY", key)
    monkeypatch.setattr(database_module, "SessionLocal", unavailable)
    monkeypatch.setattr(Fernet, "generate_key", forbidden)
    cipher = ProxyEncryption()
    encrypted = cipher.encrypt("http://synthetic.invalid:8080")
    assert cipher.decrypt(encrypted) == "http://synthetic.invalid:8080"
    assert (
        Fernet(key).decrypt(encrypted.encode()).decode()
        == "http://synthetic.invalid:8080"
    )
