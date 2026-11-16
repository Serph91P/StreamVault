"""Proxy health uses closed owning SQL scopes and scalar async handoffs."""

from threading import get_ident
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.models import ProxySettings
from app.services.proxy.proxy_health_service import ProxyHealthService
from tests import test_proxy_identity_ownership

proxy_databases = test_proxy_identity_ownership.proxy_databases


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["manual", "cycle", "selection", "stats"])
async def test_proxy_operations_keep_their_own_catalogue_closed_before_awaits(
    operation, proxy_databases
):
    databases, _ = proxy_databases
    queries, notices = [], []
    for database in databases:
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *args: queries.append(get_ident()),
        )
    for index, database in enumerate(databases):

        async def broadcast(message):
            assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
            notices.append((index, message))

        service = ProxyHealthService(
            session_factory=database.sync_session_factory,
            settings=Settings(ENVIRONMENT="test", _env_file=None),
            websocket_manager=SimpleNamespace(send_notification=broadcast),
        )
        url = f"http://owner-{index}:synthetic-password@proxy.invalid:8080"
        calls = []

        async def token():
            assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
            calls.append("token")
            return "synthetic-token"

        async def check(proxy_url, access_token):
            assert proxy_url == url and access_token == "synthetic-token"
            assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
            calls.append("check")
            return {"status": "healthy", "response_time_ms": 25, "error": None}

        service._get_twitch_access_token = token
        service._check_proxy_health = check
        queries.clear()
        if operation == "manual":
            result = await service.check_proxy_health_manual(1)
            assert result == {
                "proxy_id": 1,
                "health_status": "healthy",
                "response_time_ms": 25,
                "consecutive_failures": 0,
                "enabled": True,
                "error": None,
            }
        elif operation == "cycle":
            await service.run_health_checks()
        elif operation == "selection":
            assert await service.get_best_proxy() == url
        else:
            await service.increment_recording_stats(url, False)
        assert queries and get_ident() not in queries
        assert calls == (["token", "check"] if operation in ("manual", "cycle") else [])
        with database.sync_session_factory() as session:
            row = session.get(ProxySettings, 1)
            if operation == "stats":
                assert (
                    row.total_recordings,
                    row.failed_recordings,
                    row.success_rate,
                ) == (1, 1, 0.0)
            elif operation in ("manual", "cycle"):
                assert (
                    row.health_status == "healthy"
                    and row.average_response_time_ms == 25
                )
                assert row.last_health_check is not None
                assert notices[-1][0] == index
                assert notices[-1][1]["proxy"]["proxy_url"] == "proxy.invalid:8080"
                assert "synthetic-password" not in repr(notices)
        if index == 0:
            with databases[1].sync_session_factory() as session:
                peer = session.get(ProxySettings, 1)
                assert peer.health_status == "unknown" and peer.total_recordings == 0
        await service.stop()


@pytest.fixture
async def proxy_operation(proxy_databases):
    databases, _ = proxy_databases
    notices = []

    async def broadcast(message):
        assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
        notices.append(message)

    service = ProxyHealthService(
        session_factory=databases[0].sync_session_factory,
        settings=Settings(ENVIRONMENT="test", _env_file=None),
        websocket_manager=SimpleNamespace(send_notification=broadcast),
    )

    async def token():
        return "synthetic-token"

    async def check(*args):
        return {"status": "healthy", "response_time_ms": 25, "error": None}

    service._get_twitch_access_token = token
    service._check_proxy_health = check
    try:
        yield service, databases[0], notices
    finally:
        await service.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("manual", [False, True])
async def test_proxy_failure_budget_disables_only_automatic_checks(
    proxy_operation, manual
):
    service, database, notices = proxy_operation
    with database.sync_session_factory() as session:
        session.get(ProxySettings, 1).consecutive_failures = 2
        session.commit()

    async def failed(*args):
        return {
            "status": "failed",
            "response_time_ms": None,
            "error": "Synthetic upstream failure",
        }

    service._check_proxy_health = failed
    if manual:
        result = await service.check_proxy_health_manual(1)
        assert (
            result["health_status"] == "failed" and result["consecutive_failures"] == 3
        )
    else:
        await service.run_health_checks()
    with database.sync_session_factory() as session:
        row = session.get(ProxySettings, 1)
        assert row.consecutive_failures == 3 and row.enabled is manual
        assert row.health_status == "failed"
    assert notices[0]["auto_disabled"] is not manual


@pytest.mark.asyncio
async def test_proxy_changed_during_http_is_not_overwritten_or_announced(
    proxy_operation,
):
    service, database, notices = proxy_operation

    async def changed(*args):
        from app.utils.proxy_encryption import get_proxy_encryption

        with database.sync_session_factory() as session:
            get_proxy_encryption(session)
            row = session.get(ProxySettings, 1)
            row.proxy_url = (
                "http://replacement:synthetic-password@replacement.invalid:8080"
            )
            session.commit()
        return {"status": "healthy", "response_time_ms": 25, "error": None}

    service._check_proxy_health = changed
    assert await service.check_proxy_health_manual(1) == {
        "error": "Proxy changed during health check"
    }
    with database.sync_session_factory() as session:
        from app.utils.proxy_encryption import get_proxy_encryption

        get_proxy_encryption(session)
        row = session.get(ProxySettings, 1)
        assert (
            row.proxy_url
            == "http://replacement:synthetic-password@replacement.invalid:8080"
        )
        assert row.health_status == "unknown" and row.last_health_check is None
    assert notices == []


@pytest.mark.asyncio
async def test_proxy_publication_rolls_back_and_retries_without_false_notice(
    proxy_operation,
):
    service, database, notices = proxy_operation
    injected = []

    def fail_update(connection, cursor, statement, *args):
        if statement.startswith("UPDATE proxy_settings") and not injected:
            injected.append(True)
            raise RuntimeError("Synthetic persistence failure")

    event.listen(database.sync_engine, "before_cursor_execute", fail_update)
    with pytest.raises(RuntimeError, match="Synthetic persistence failure"):
        await service.check_proxy_health_manual(1)
    with database.sync_session_factory() as session:
        row = session.get(ProxySettings, 1)
        assert row.health_status == "unknown" and row.last_health_check is None
    assert notices == []
    assert (await service.check_proxy_health_manual(1))["health_status"] == "healthy"
    assert len(notices) == 1


@pytest.mark.asyncio
async def test_proxy_publication_cancellation_drains_before_return(proxy_operation):
    import asyncio
    from threading import Event

    service, database, notices = proxy_operation
    entered, release = Event(), Event()

    def held_update(connection, cursor, statement, *args):
        if statement.startswith("UPDATE proxy_settings"):
            entered.set()
            assert release.wait(5)

    event.listen(database.sync_engine, "before_cursor_execute", held_update)
    task = asyncio.create_task(service.check_proxy_health_manual(1))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert database.sync_engine.pool.checkedout() == 0
    with database.sync_session_factory() as session:
        assert session.get(ProxySettings, 1).health_status == "healthy"
    assert notices == []


@pytest.mark.asyncio
async def test_proxy_policy_reads_and_running_loop_are_owner_scoped(proxy_operation):
    import asyncio
    from app.models import RecordingSettings

    service, database, notices = proxy_operation
    with database.sync_session_factory() as session:
        session.add(
            RecordingSettings(
                proxy_health_check_interval_seconds=45,
                proxy_health_check_enabled=True,
                proxy_max_consecutive_failures=5,
            )
        )
        session.commit()
    assert await service._get_check_interval() == 45
    assert await service._are_checks_enabled() is True
    assert await service._get_max_failures() == 5
    await service.start()
    for _ in range(200):
        if notices:
            break
        await asyncio.sleep(0.01)
    assert len(notices) == 1
    assert service._background_task is not None and not service._background_task.done()
    await service.stop()
    assert service._background_task.done() and service._running is False
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_missing_proxy_and_empty_catalogue_never_attempt_provider_io(
    proxy_operation,
):
    service, database, notices = proxy_operation

    async def forbidden():
        raise AssertionError("Provider must not be contacted")

    service._get_twitch_access_token = forbidden
    assert await service.check_proxy_health_manual(99) == {"error": "Proxy not found"}
    with database.sync_session_factory() as session:
        session.query(ProxySettings).delete()
        session.commit()
    await service.run_health_checks()
    assert await service.get_best_proxy() is None
    await service.increment_recording_stats("http://missing.invalid:8080", False)
    assert notices == []


@pytest.mark.asyncio
async def test_policy_failure_is_private_recoverable_and_disabled_loop_is_stoppable(
    proxy_operation, caplog
):
    import asyncio
    from app.models import RecordingSettings

    service, database, notices = proxy_operation
    injected = []
    completed = asyncio.Event()
    with database.sync_session_factory() as session:
        session.add(RecordingSettings(proxy_health_check_enabled=False))
        session.commit()

    def fail_read(connection, cursor, statement, *args):
        if "FROM recording_settings" in statement and not injected:
            injected.append(True)
            raise RuntimeError("synthetic-policy-private-marker")

    event.listen(database.sync_engine, "before_cursor_execute", fail_read)
    assert await service._get_check_interval() == 300
    assert "synthetic-policy-private-marker" not in caplog.text
    native_enabled = service._are_checks_enabled

    async def checked_enabled():
        result = await native_enabled()
        assert result is False
        completed.set()
        return result

    service._are_checks_enabled = checked_enabled
    await service.start()
    await asyncio.wait_for(completed.wait(), 5)
    await service.stop()
    assert service._background_task.done() and notices == []
