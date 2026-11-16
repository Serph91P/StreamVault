"""Apprise uses owned, closed worker snapshots before real loopback delivery."""

import asyncio
from threading import get_ident

import pytest
from aiohttp import web
from sqlalchemy import event

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import GlobalSettings, Streamer
from app.services.notifications import external_notification_service as module
from app.utils.async_db_utils import run_in_thread_pool


@pytest.fixture
async def notification_catalogs(tmp_path):
    databases = []
    try:
        for name in ("first", "second"):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
            databases.append(database)
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(GlobalSettings(id=1, notifications_enabled=True))
                session.add(
                    Streamer(
                        id=1,
                        username="channel",
                        twitch_id=name,
                        profile_image_url="/recordings/.media/profiles/profile_avatar_1.jpg",
                    )
                )
                session.commit()
        yield databases
    finally:
        for database in databases:
            await database.adispose()


@pytest.mark.asyncio
async def test_external_constructor_does_not_query_default_catalog(
    notification_catalogs, monkeypatch
):
    database = notification_catalogs[0]
    queries = []
    event.listen(
        database.sync_engine,
        "before_cursor_execute",
        lambda *args: queries.append(get_ident()),
    )
    monkeypatch.setattr(module, "SessionLocal", database.sync_session_factory)
    service = module.ExternalNotificationService()
    assert service.apprise is not None
    assert queries == [], (
        "Construction must not read a global catalog on the event loop"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["basic", "stream", "recording", "test"])
async def test_external_delivery_uses_closed_owned_worker_catalogs(
    notification_catalogs, operation, monkeypatch
):
    databases = notification_catalogs
    loop_thread = get_ident()
    queries, received = [], []

    def forbidden_default():
        raise AssertionError("Owned notifications must not read the legacy catalog")

    monkeypatch.setattr(module, "SessionLocal", forbidden_default)

    async def receive(request):
        owner = int(request.match_info["owner"].removeprefix("owner-"))
        assert databases[owner].sync_engine.pool.checkedout() == 0
        received.append((request.match_info["owner"], await request.json()))
        return web.Response(status=200)

    provider = web.Application()
    provider.router.add_post("/{owner}", receive)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    services = []
    try:
        for index, database in enumerate(databases):
            with database.sync_session_factory() as session:
                row = session.get(GlobalSettings, 1)
                row.notification_url = f"json://127.0.0.1:{port}/owner-{index}"
                row.notify_recording_completed = index == 0
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *args: queries.append(get_ident()),
            )
            services.append(
                module.ExternalNotificationService(
                    session_factory=database.sync_session_factory,
                    settings=Settings(
                        ENVIRONMENT="test",
                        BASE_URL=f"https://owner-{index}.invalid",
                        _env_file=None,
                    ),
                )
            )
        assert queries == []
        if operation == "basic":
            results = await asyncio.gather(
                *(
                    service.send_notification("literal message", "literal title")
                    for service in services
                )
            )
        elif operation == "stream":
            results = await asyncio.gather(
                *(
                    service.send_stream_notification(
                        "CHANNEL",
                        "online",
                        {"title": "literal title", "category_name": "Games"},
                    )
                    for service in services
                )
            )
        elif operation == "recording":
            results = await asyncio.gather(
                *(
                    service.send_recording_notification(
                        "channel",
                        "recording_completed",
                        {"duration_minutes": 150, "quality": "720p"},
                    )
                    for service in services
                )
            )
        else:
            results = await asyncio.gather(
                *(service.send_test_notification() for service in services)
            )
        assert results == ([True, False] if operation == "recording" else [True, True])
        assert sorted(owner for owner, _ in received) == (
            ["owner-0"] if operation == "recording" else ["owner-0", "owner-1"]
        )
        assert queries and loop_thread not in queries
        for _, payload in received:
            if operation == "basic":
                assert payload["title"] == "literal title"
                assert payload["message"] == "literal message"
            elif operation == "recording":
                assert "2h 30m" in payload["message"]
                assert "720p" in payload["message"]
            elif operation == "stream":
                assert "literal title" in payload["message"]
            else:
                assert "test notification from StreamVault" in payload["message"]

        # Re-read current policy on each operation; a peer's disabled state cannot leak.
        def disable():
            with databases[0].sync_session_factory() as session:
                session.get(GlobalSettings, 1).notifications_enabled = False
                session.commit()

        await run_in_thread_pool(disable)
        before = len(received)
        assert await services[0].send_notification("disabled") is False
        assert await services[1].send_notification("still enabled") is True
        assert len(received) == before + 1 and received[-1][0] == "owner-1"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_external_catalog_errors_are_false_and_do_not_expose_credentials(caplog):
    loop_thread = get_ident()
    threads = []

    def broken_catalog():
        threads.append(get_ident())
        raise RuntimeError("fixture-private-notification-credential")

    service = module.ExternalNotificationService(session_factory=broken_catalog)
    assert await service.send_notification("message") is False
    assert await service.send_stream_notification("channel", "online", {}) is False
    assert (
        await service.send_recording_notification("channel", "recording_completed")
        is False
    )
    assert await service.send_test_notification() is False
    assert len(threads) == 4 and loop_thread not in threads
    assert "fixture-private-notification-credential" not in caplog.text


@pytest.mark.parametrize(
    "scheme",
    [
        "ntfy",
        "discord",
        "telegram",
        "matrix",
        "slack",
        "pover",
        "gotify",
        "pbul",
        "msteams",
        "json",
    ],
)
def test_external_service_configuration_preserves_urls_without_logging_credentials(
    scheme, caplog
):
    caplog.set_level("DEBUG", logger="streamvault")
    base = f"{scheme}://fixture-notification-credential@localhost/topic"
    service = module.ExternalNotificationService()
    result = service._get_service_specific_url(
        base,
        "https://twitch.tv/channel",
        "https://images.invalid/avatar.png",
        "channel",
        "online",
    )
    assert result.startswith(base)
    assert "fixture-notification-credential" not in caplog.text


@pytest.mark.asyncio
async def test_external_preparation_cancellation_drains_catalog_before_return(
    notification_catalogs,
):
    from threading import Event

    database = notification_catalogs[0]
    entered, release = asyncio.Event(), Event()
    loop = asyncio.get_running_loop()

    def hold(*args):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5), "Test must release its own catalog worker"

    event.listen(database.sync_engine, "before_cursor_execute", hold)
    service = module.ExternalNotificationService(
        session_factory=database.sync_session_factory
    )
    task = asyncio.create_task(service.send_notification("cancelled"))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert database.sync_engine.pool.checkedout() == 1
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "Cancellation must await its still-open worker session"
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        event.remove(database.sync_engine, "before_cursor_execute", hold)
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["basic", "stream", "recording", "test"])
async def test_external_delivery_cancellation_keeps_ownership_until_http_finishes(
    notification_catalogs, operation
):
    database = notification_catalogs[0]
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(request):
        assert database.sync_engine.pool.checkedout() == 0
        entered.set()
        await release.wait()
        return web.Response(status=200)

    provider = web.Application()
    provider.router.add_post("/notify", hold)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    with database.sync_session_factory() as session:
        session.get(
            GlobalSettings, 1
        ).notification_url = f"json://127.0.0.1:{port}/notify"
        session.get(GlobalSettings, 1).notify_recording_completed = True
        session.commit()
    service = module.ExternalNotificationService(
        session_factory=database.sync_session_factory
    )
    if operation == "basic":
        call = service.send_notification("cancelled")
    elif operation == "stream":
        call = service.send_stream_notification("channel", "online", {})
    elif operation == "recording":
        call = service.send_recording_notification("channel", "recording_completed")
    else:
        call = service.send_test_notification()
    task = asyncio.create_task(call)
    try:
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 0.05)
        assert not task.done(), (
            "Apprise executor HTTP must remain owned after cancellation"
        )
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await runner.cleanup()
