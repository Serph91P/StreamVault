"""Post-migration proxy identities are explicit, persistent and factory-owned."""

import pytest
from cryptography.fernet import Fernet

from app import database as database_module
from app.database import Base, DatabaseLifecycle
from app.models import GlobalSettings
from app.utils import proxy_encryption
from test_video_catalog_timestamps import catalog_sessions


@pytest.mark.parametrize("catalog_sessions", ["postgres"], indirect=True)
def test_postgres_proxy_bootstrap_concurrent_first_start_and_held_lock_deadline(
    catalog_sessions,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from time import monotonic
    from sqlalchemy import text

    factory, _ = catalog_sessions
    engine = factory.kw["bind"]
    Base.metadata.create_all(engine, tables=[GlobalSettings.__table__])
    barrier = Barrier(2)

    def initialize():
        barrier.wait(timeout=5)
        return proxy_encryption.bootstrap_proxy_identity(factory)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(initialize) for _ in range(2)]
        ciphers = [future.result(timeout=10) for future in futures]
    encrypted = ciphers[0].encrypt("http://synthetic.invalid:8080")
    assert ciphers[1].decrypt(encrypted) == "http://synthetic.invalid:8080"
    with factory() as session:
        assert session.query(GlobalSettings).count() == 1
        key = session.query(GlobalSettings).one().proxy_encryption_key
    with engine.begin() as holder:
        holder.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": 7_314_908_422}
        )
        begin = monotonic()
        with pytest.raises(RuntimeError, match="Persistent proxy identity unavailable"):
            proxy_encryption.bootstrap_proxy_identity(factory, timeout_seconds=0.05)
        assert monotonic() - begin < 1
    with factory() as session:
        assert session.query(GlobalSettings).one().proxy_encryption_key == key
        assert (
            proxy_encryption.get_cached_proxy_encryption(session).decrypt(encrypted)
            == "http://synthetic.invalid:8080"
        )


@pytest.mark.asyncio
async def test_standalone_proxy_adapter_reloads_existing_identity_and_cached_model(
    tmp_path, monkeypatch
):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'standalone-identity.db'}")
    key = Fernet.generate_key().decode()
    try:
        with lifecycle.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(GlobalSettings(proxy_encryption_key=key))
            session.commit()
        monkeypatch.setattr(
            database_module, "SessionLocal", lifecycle.sync_session_factory
        )
        monkeypatch.setattr(proxy_encryption, "_proxy_encryption", None)
        first = proxy_encryption.get_proxy_encryption()
        assert proxy_encryption.get_cached_proxy_encryption() is first
        encrypted = first.encrypt("http://synthetic.invalid:8080")
        restored = proxy_encryption.ProxyEncryption()
        assert restored.decrypt(encrypted) == "http://synthetic.invalid:8080"
        with lifecycle.sync_session_factory() as session:
            assert session.query(GlobalSettings).one().proxy_encryption_key == key
        assert lifecycle.sync_engine.pool.checkedout() == 0
    finally:
        await lifecycle.adispose()


@pytest.mark.asyncio
async def test_invalid_existing_proxy_bootstrap_identity_is_not_replaced_or_cached(
    tmp_path, monkeypatch
):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'invalid-identity.db'}")

    def forbidden():
        raise AssertionError("existing invalid identity was replaced")

    monkeypatch.setattr(Fernet, "generate_key", forbidden)
    try:
        with lifecycle.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(GlobalSettings(proxy_encryption_key="synthetic-invalid-key"))
            session.commit()
        with pytest.raises(RuntimeError, match="Persistent proxy identity unavailable"):
            proxy_encryption.bootstrap_proxy_identity(lifecycle.sync_session_factory)
        assert (
            "streamvault.proxy_encryption"
            not in lifecycle.sync_session_factory.kw.get("info", {})
        )
        with lifecycle.sync_session_factory() as session:
            assert (
                session.query(GlobalSettings).one().proxy_encryption_key
                == "synthetic-invalid-key"
            )
        assert lifecycle.sync_engine.pool.checkedout() == 0
    finally:
        await lifecycle.adispose()


@pytest.mark.asyncio
async def test_explicit_proxy_bootstrap_initializes_only_owned_factory_and_never_rotates(
    tmp_path, monkeypatch
):
    assert hasattr(proxy_encryption, "bootstrap_proxy_identity"), (
        "proxy identity has no explicit post-migration bootstrap"
    )
    databases = []
    old_key = Fernet.generate_key().decode()
    defaults = []

    def forbidden():
        defaults.append(True)
        raise AssertionError("proxy bootstrap borrowed default catalogue")

    monkeypatch.setattr(database_module, "SessionLocal", forbidden)
    try:
        for index in range(2):
            lifecycle = DatabaseLifecycle(
                f"sqlite:///{tmp_path / f'identity-{index}.db'}"
            )
            databases.append(lifecycle)
            with lifecycle.sync_engine.begin() as connection:
                Base.metadata.create_all(connection)
            with lifecycle.sync_session_factory() as session:
                if index:
                    session.add(GlobalSettings(proxy_encryption_key=old_key))
                session.commit()
        for index, lifecycle in enumerate(databases):
            factory = lifecycle.sync_session_factory
            cipher = proxy_encryption.bootstrap_proxy_identity(factory)
            with factory() as session:
                stored = session.query(GlobalSettings).one().proxy_encryption_key
                assert stored
                if index:
                    assert stored == old_key
                assert session.info["streamvault.proxy_encryption"] is cipher
            encrypted = cipher.encrypt("http://synthetic.invalid:8080")
            assert (
                Fernet(stored).decrypt(encrypted.encode()).decode()
                == "http://synthetic.invalid:8080"
            )
            repeated = proxy_encryption.bootstrap_proxy_identity(factory)
            assert repeated.decrypt(encrypted) == "http://synthetic.invalid:8080"
            with factory() as session:
                assert (
                    session.query(GlobalSettings).one().proxy_encryption_key == stored
                )
            assert lifecycle.sync_engine.pool.checkedout() == 0
        assert not defaults
    finally:
        for lifecycle in databases:
            await lifecycle.adispose()
