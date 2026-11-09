"""Post-migration proxy identities are explicit, persistent and factory-owned."""

import pytest
from cryptography.fernet import Fernet

from app import database as database_module
from app.database import Base, DatabaseLifecycle
from app.models import GlobalSettings
from app.utils import proxy_encryption


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
                session.add(
                    GlobalSettings(proxy_encryption_key=old_key if index else None)
                )
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
