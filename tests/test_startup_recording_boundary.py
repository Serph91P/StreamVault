"""Startup snapshots→real owned HTTP→controlled admission/physical-death effects."""

import asyncio
import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from threading import get_ident

import pytest
from aiohttp import web
from sqlalchemy import event, inspect
from sqlalchemy.engine import make_url
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.models import Recording, Stream, Streamer, StreamMetadata, TwitchUpstreamLease
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_startup_recovery_keeps_closed_snapshots_owner_and_failure_boundaries(
    tmp_path, monkeypatch
):
    startup = importlib.import_module("app.services.init.startup_init")
    databases, applications, services, children = [], [], [], []
    queries, probes, requests, admissions = [], [], [], []
    loop_thread = get_ident()
    kinds = ("success", "failed", "active", "unknown", "dead", "api-error", "no-lease")
    now = datetime.now(timezone.utc)

    async def streams(request):
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        twitch_id = request.query["user_id"]
        owner, kind = twitch_id.split(":", 1)
        assert request.headers["Client-ID"] == owner
        requests.append(twitch_id)
        if kind == "api-error":
            return web.Response(status=403)
        return web.json_response(
            {
                "data": [{"id": "live"}]
                if kind in {"success", "failed", "no-lease"}
                else []
            }
        )

    provider = web.Application()
    provider.router.add_get("/helix/streams", streams)
    runner = web.AppRunner(provider)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    native_stat = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        for owner in ("first", "second"):
            root = tmp_path / owner
            root.mkdir()
            metadata_segments = root / "metadata_segments"
            fallback_segments = root / "fallback_segments"
            metadata_segments.mkdir()
            fallback_segments.mkdir()
            if postgres_url := os.environ.get("STREAMVAULT_STARTUP_TEST_URL"):
                url = make_url(postgres_url)
                assert url.get_backend_name() == "postgresql"
                database = DatabaseLifecycle(
                    url.set(database=f"startup_{owner}").render_as_string(
                        hide_password=False
                    )
                )
            else:
                database = DatabaseLifecycle(f"sqlite:///{root / 'owned.db'}")
            databases.append(database)
            assert not inspect(database.sync_engine).get_table_names(), (
                "probe requires empty owned databases"
            )
            with database.sync_engine.begin() as connection:
                if database.sync_engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                for index, kind in enumerate(kinds):
                    session.add(
                        Streamer(
                            id=index + 1, username=kind, twitch_id=f"{owner}:{kind}"
                        )
                    )
                    session.flush()
                    session.add(
                        Stream(
                            id=index + 70,
                            streamer_id=index + 1,
                            started_at=now - timedelta(hours=2),
                        )
                    )
                    session.flush()
                    session.add(
                        Recording(
                            id=index + 7,
                            stream_id=index + 70,
                            status="recording",
                            start_time=now - timedelta(hours=1),
                            duration=17,
                            path=str(root / "fallback.ts")
                            if kind == "failed"
                            else None,
                        )
                    )
                    session.flush()
                    if kind == "success":
                        session.add(
                            StreamMetadata(
                                stream_id=index + 70,
                                segments_dir_path=str(metadata_segments),
                            )
                        )
                    if kind in {"success", "failed"}:
                        session.add(
                            TwitchUpstreamLease(
                                channel_key=f"{owner}:{kind}",
                                recording_id=index + 7,
                                purpose="RECORDING",
                                state="ACTIVE",
                                generation=11,
                                reserved_at=now,
                                heartbeat_at=now,
                                created_at=now,
                                updated_at=now,
                                expires_at=now + timedelta(hours=1),
                            )
                        )
                session.commit()
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    TWITCH_APP_ID=owner,
                    TWITCH_APP_SECRET="fixture",
                    RECORDING_DIRECTORY=str(root),
                    _env_file=None,
                ),
                database=database,
            )
            applications.append(app)
            service = await run_in_thread_pool(
                dependencies.get_application_recovery_service,
                HTTPConnection({"type": "http", "app": app, "headers": []}),
            )
            services.append(service)
            service.twitch_api.base_url = f"http://127.0.0.1:{port}/helix"
            service.twitch_api._access_token = "fixture-owned-token"
            service.twitch_api._token_expires_at = float("inf")
            recorder = service.recording_manager
            recorder.orchestrator.state_manager.add_active_recording(
                9, {"stream_id": 72}
            )
            child = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
            children.append(child)
            await child.wait()
            recorder.process_manager.active_processes["stream_74"] = child

            async def admit(
                *,
                stream_id,
                streamer_id,
                owner=owner,
                database=database,
                root=root,
                **kwargs,
            ):
                assert database.sync_engine.pool.checkedout() == 0
                assert (
                    kwargs["force_mode"] is True and kwargs["recovery_generation"] == 11
                )
                assert kwargs["resume_segments_dir"] == str(
                    root
                    / ("metadata_segments" if stream_id == 70 else "fallback_segments")
                )
                admissions.append((owner, stream_id, streamer_id))
                return 9000 if stream_id == 70 else None

            monkeypatch.setattr(recorder, "start_recording", admit)
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
        for index, (service, database) in enumerate(
            zip(services, databases, strict=True)
        ):
            queries.clear()
            with monkeypatch.context() as watched:
                watched.setattr(os, "stat", stat)
                await startup.cleanup_zombie_recordings(
                    session_factory=database.sync_session_factory,
                    recording_manager=service.recording_manager,
                    twitch_api=service.twitch_api,
                )
            assert queries and loop_thread not in queries
            assert probes and loop_thread not in probes
            with database.sync_session_factory() as session:
                for offset, kind in enumerate(kinds):
                    row = session.get(Recording, offset + 7)
                    assert row.status == (
                        "stopped" if kind in {"success", "dead"} else "recording"
                    )
                    if kind in {"success", "dead"}:
                        assert row.end_time is not None and row.duration >= 3600
                    else:
                        assert row.end_time is None and row.duration == 17
                    assert (session.get(Stream, offset + 70).ended_at is not None) is (
                        kind == "dead"
                    )
            if index == 0:
                with databases[1].sync_session_factory() as session:
                    assert all(
                        row.status == "recording" for row in session.query(Recording)
                    )
        assert admissions == [
            ("first", 70, 1),
            ("first", 71, 2),
            ("second", 70, 1),
            ("second", 71, 2),
        ]
        assert not any(value.endswith(":active") for value in requests)
        assert len(requests) == 12
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
                await child.wait()
        for service in services:
            service.recording_manager.process_manager.active_processes.pop(
                "stream_74", None
            )
            service.recording_manager.orchestrator.state_manager.clear_all_state()
            await service.twitch_api.close()
            await service.recording_manager.shutdown()
        for app in applications:
            await app.state.websocket_manager.close_all()
        for database in databases:
            await database.adispose()
        await runner.cleanup()
