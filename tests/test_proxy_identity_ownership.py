"""Mapped proxy credentials must use their existing owning database identity."""

from cryptography.fernet import Fernet
import pytest

from app.database import Base, DatabaseLifecycle
from app.models import GlobalSettings, ProxySettings
from app.utils import proxy_encryption


@pytest.fixture
async def proxy_databases(tmp_path, monkeypatch):
    databases, identities = [], []
    try:
        for index in range(2):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path}/owner-{index}.db")
            databases.append(database)
            key = Fernet.generate_key()
            identities.append(key)
            with database.sync_engine.begin() as connection:
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(GlobalSettings(proxy_encryption_key=key.decode()))
                session.add(
                    ProxySettings(
                        id=1,
                        _proxy_url_encrypted=Fernet(key)
                        .encrypt(
                            f"http://owner-{index}:synthetic-password@proxy.invalid:8080".encode()
                        )
                        .decode(),
                    )
                )
                session.commit()
        yield databases, identities
    finally:
        for database in databases:
            await database.adispose()


class ForbiddenForeignCipher:
    def encrypt(self, value):
        raise AssertionError("Foreign proxy identity used")

    decrypt = encrypt


def forbid_new_identity():
    raise AssertionError("Existing proxy identity must not be replaced")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["read", "write"])
async def test_unprepared_proxy_property_never_performs_hidden_sql(
    proxy_databases, operation
):
    from sqlalchemy import event

    databases, _ = proxy_databases
    for database in databases:
        observed = []
        with database.sync_session_factory() as session:
            proxy = session.get(ProxySettings, 1)

            def forbidden(*_):
                observed.append(True)
                raise AssertionError("ORM proxy property attempted hidden SQL")

            event.listen(database.sync_engine, "before_cursor_execute", forbidden)
            try:
                if operation == "read":
                    assert proxy.proxy_url == ""
                else:
                    with pytest.raises(RuntimeError, match="not initialized"):
                        proxy.proxy_url = "http://synthetic.invalid:8080"
                assert not observed
            finally:
                event.remove(database.sync_engine, "before_cursor_execute", forbidden)


@pytest.mark.asyncio
async def test_mapped_proxy_roundtrip_uses_existing_owner_key_without_rotation(
    proxy_databases, monkeypatch
):
    databases, keys = proxy_databases
    monkeypatch.setattr(proxy_encryption, "_proxy_encryption", ForbiddenForeignCipher())
    monkeypatch.setattr(Fernet, "generate_key", forbid_new_identity)
    for index, database in enumerate(databases):
        with database.sync_session_factory() as session:
            proxy_encryption.get_proxy_encryption(session)
            proxy = session.get(ProxySettings, 1)
            assert (
                proxy.proxy_url
                == f"http://owner-{index}:synthetic-password@proxy.invalid:8080"
            )
            assert proxy.to_dict()["proxy_url"] == "proxy.invalid:8080"
            proxy.proxy_url = f"http://owner-{index}:replacement-synthetic-password@proxy.invalid:8080"
            session.commit()
        with database.sync_session_factory() as session:
            proxy_encryption.get_proxy_encryption(session)
            proxy = session.get(ProxySettings, 1)
            assert (
                proxy.proxy_url
                == f"http://owner-{index}:replacement-synthetic-password@proxy.invalid:8080"
            )
            assert (
                Fernet(keys[index])
                .decrypt(proxy._proxy_url_encrypted.encode())
                .decode()
                == proxy.proxy_url
            )
            assert (
                session.query(GlobalSettings).one().proxy_encryption_key
                == keys[index].decode()
            )
            assert session.query(ProxySettings).count() == 1
        assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_attached_new_proxy_does_not_autoflush_incomplete_row_or_generate_keys(
    proxy_databases, monkeypatch
):
    databases, keys = proxy_databases
    monkeypatch.setattr(proxy_encryption, "_proxy_encryption", ForbiddenForeignCipher())
    monkeypatch.setattr(Fernet, "generate_key", forbid_new_identity)
    for index, database in enumerate(databases):
        with database.sync_session_factory() as session:
            proxy_encryption.get_proxy_encryption(session)
            proxy = ProxySettings()
            session.add(proxy)
            proxy.proxy_url = (
                f"http://new-owner-{index}:synthetic-password@proxy.invalid:8080"
            )
            session.commit()
            assert proxy.id == 2
            assert (
                Fernet(keys[index])
                .decrypt(proxy._proxy_url_encrypted.encode())
                .decode()
                == proxy.proxy_url
            )
            assert (
                session.query(GlobalSettings).one().proxy_encryption_key
                == keys[index].decode()
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["absent", "empty", "invalid"])
async def test_owner_cipher_failure_never_generates_or_replaces_persisted_identity(
    state, proxy_databases, monkeypatch
):
    databases, _ = proxy_databases
    monkeypatch.setattr(proxy_encryption, "_proxy_encryption", ForbiddenForeignCipher())
    monkeypatch.setattr(Fernet, "generate_key", forbid_new_identity)
    database = databases[0]
    with database.sync_session_factory() as session:
        stored = session.query(GlobalSettings).one()
        if state == "absent":
            session.delete(stored)
        else:
            stored.proxy_encryption_key = (
                "" if state == "empty" else "synthetic-invalid-key"
            )
        session.commit()
    with database.sync_session_factory() as session:
        before = session.get(ProxySettings, 1)._proxy_url_encrypted
        with pytest.raises(ValueError if state == "invalid" else RuntimeError):
            proxy_encryption.get_proxy_encryption(session)
        assert session.get(ProxySettings, 1)._proxy_url_encrypted == before
        assert not session.new and not session.dirty and not session.deleted
        if state == "absent":
            assert session.query(GlobalSettings).count() == 0
        else:
            assert session.query(GlobalSettings).one().proxy_encryption_key == (
                "" if state == "empty" else "synthetic-invalid-key"
            )
