"""Real recovery DB→closed scalar→owned HTTP, without global registries."""

import asyncio
from datetime import datetime, timezone
from threading import get_ident

import pytest
from aiohttp import web
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.models import Recording, Stream, Streamer
from app.services.api.twitch_api import TwitchAPIService
from app.services.recording.unified_recovery_service import UnifiedRecoveryService
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_recovery_live_probe_closes_owned_worker_session_before_http(
    tmp_path, monkeypatch
):
    databases, applications, services, clients = [], [], [], []
    queries, seen = [], []
    loop_thread = get_ident()

    async def forbidden_global(*args, **kwargs):
        raise AssertionError("Recovery must never borrow the default provider")

    from app.services.api.twitch_api import twitch_api

    monkeypatch.setattr(twitch_api, "get_streams", forbidden_global)

    async def streams(request):
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        seen.append((request.query["user_id"], request.headers["Client-ID"]))
        index = 0 if request.headers["Client-ID"] == "first" else 1
        assert request.headers["Authorization"] == f"Bearer owner-{index}"
        return web.json_response({"data": [{"id": "42"}] if index == 0 else []})

    provider = web.Application()
    provider.router.add_get("/helix/streams", streams)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        for index, name in enumerate(("first", "second")):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
            databases.append(database)
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username=name, twitch_id=f"upstream-{name}"))
                session.flush()
                session.add(Stream(id=70, streamer_id=1, title=name))
                session.flush()
                session.add(
                    Recording(
                        id=7,
                        stream_id=70,
                        status="recording",
                        start_time=datetime.now(timezone.utc),
                    )
                )
                session.commit()
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    TWITCH_APP_ID=name,
                    TWITCH_APP_SECRET=f"{name}-fixture",
                    RECORDING_DIRECTORY=str(tmp_path / name),
                    _env_file=None,
                ),
                database=database,
            )
            applications.append(app)
            recorder = await run_in_thread_pool(
                dependencies.get_application_recording_manager,
                HTTPConnection({"type": "http", "app": app, "headers": []}),
            )
            client = TwitchAPIService(settings=app.state.settings)
            clients.append(client)
            client.base_url = f"http://127.0.0.1:{port}/helix"
            client._access_token = f"owner-{index}"
            client._token_expires_at = float("inf")
            services.append(
                UnifiedRecoveryService(
                    session_factory=database.sync_session_factory,
                    settings=app.state.settings,
                    recording_manager=recorder,
                    queue_service=app.state.background_queue_service,
                    twitch_api=client,
                )
            )
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
        assert await asyncio.gather(
            *(service._check_if_streamer_still_live(7) for service in services)
        ) == [True, False]
        assert queries and loop_thread not in queries
        assert sorted(seen) == [
            ("upstream-first", "first"),
            ("upstream-second", "second"),
        ]
        assert await services[0]._check_if_streamer_still_live(999) is False
        assert len(seen) == 2
        await clients[0].close()
        assert await services[1]._check_if_streamer_still_live(7) is False
        assert len(seen) == 3
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        for client in clients:
            await client.close()
        for app in applications:
            await app.state.websocket_manager.close_all()
        for database in databases:
            await database.adispose()
        await runner.cleanup()
