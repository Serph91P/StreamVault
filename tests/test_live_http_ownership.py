"""Live HTTP/HLS state belongs to the application that admitted the viewer."""

import asyncio
import importlib
import sys
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace

import pytest
from starlette.requests import HTTPConnection

from app.routes import live as live_routes

from app.lifespan import _close_application_twitch
from app.services.live_streaming_service import LiveStreamSession, LiveStreamingService
from app.services.live_streaming_service import LiveStreamStartResult
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
async def test_live_http_and_hls_select_only_their_app_state(
    image_applications, monkeypatch
):
    applications, databases, clients, _ = image_applications
    actors, children = [], []
    try:
        for index, app in enumerate(applications):
            actor = LiveStreamingService(
                session_factory=databases[index].sync_session_factory,
                settings=app.state.settings,
            )
            app.state.live_streaming_service = actor
            actors.append(actor)
            root = Path(app.state.settings.RECORDING_DIRECTORY) / "live-probe"
            root.mkdir()
            (root / "playlist.m3u8").write_text("#EXTM3U\nsegment.ts\n")
            (root / "segment.ts").write_bytes(f"owner-{index}".encode())
            pair = [
                await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
                for _ in range(2)
            ]
            children.extend(pair)
            await asyncio.gather(*(child.wait() for child in pair))
            actor.sessions["shared-id"] = LiveStreamSession(
                "shared-id",
                f"owner-{index}",
                "best",
                pair[0],
                pair[1],
                root,
                user_id="1",
            )
        assert actors[0] is not actors[1]
        paths = {
            session.output_dir / name
            for actor in actors
            for session in actor.sessions.values()
            for name in ("playlist.m3u8", "segment.ts")
        }
        file_threads = []
        native_exists, native_read = Path.exists, Path.read_text

        def exists(path):
            if path in paths:
                file_threads.append(get_ident())
            return native_exists(path)

        def read(path, *args, **kwargs):
            if path in paths:
                file_threads.append(get_ident())
            return native_read(path, *args, **kwargs)

        monkeypatch.setattr(Path, "exists", exists)
        monkeypatch.setattr(Path, "read_text", read)
        for index, client in enumerate(clients):
            own = actors[index].sessions["shared-id"]
            status = await client.get("/api/live/status/shared-id")
            assert status.status_code == 200
            assert status.json()["streamer_name"] == f"owner-{index}"
            active = await client.get("/api/live/active")
            assert active.status_code == 200
            assert [row["streamer_name"] for row in active.json()["streams"]] == [
                f"owner-{index}"
            ]
            playlist = await client.get(
                "/api/live/stream/shared-id/playlist.m3u8",
                params={"token": own.playback_token},
            )
            assert playlist.status_code == 200
            assert f"segment.ts?token={own.playback_token}" in playlist.text
            segment = await client.get(
                "/api/live/stream/shared-id/segment.ts",
                params={"token": own.playback_token},
            )
            assert (
                segment.status_code == 200
                and segment.content == f"owner-{index}".encode()
            )
            foreign = actors[1 - index].sessions["shared-id"].playback_token
            assert (
                await client.get(
                    "/api/live/stream/shared-id/playlist.m3u8",
                    params={"token": foreign},
                )
            ).status_code == 403
            assert (await client.get("/api/live/status/missing")).status_code == 404
            assert (
                await client.get(
                    "/api/live/stream/missing/playlist.m3u8",
                    params={"token": own.playback_token},
                )
            ).status_code == 404
            assert (
                await client.get(
                    "/api/live/stream/missing/segment.ts",
                    params={"token": own.playback_token},
                )
            ).status_code == 404
            assert (
                await client.get(
                    "/api/live/stream/shared-id/segment.ts", params={"token": foreign}
                )
            ).status_code == 403
            assert (
                await client.get(
                    "/api/live/stream/shared-id/absent.ts",
                    params={"token": own.playback_token},
                )
            ).status_code == 404
        stopped = await clients[0].delete("/api/live/stop/shared-id")
        assert stopped.status_code == 200 and stopped.json()["success"] is True
        assert (await clients[0].get("/api/live/status/shared-id")).status_code == 404
        assert (await clients[1].get("/api/live/status/shared-id")).status_code == 200
        pending = actors[1].sessions["shared-id"]

        def failed_read(path, *args, **kwargs):
            if path == pending.playlist_path:
                raise OSError("fixture unavailable playlist")
            return read(path, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(Path, "read_text", failed_read)
            failed = await clients[1].get(
                "/api/live/stream/shared-id/playlist.m3u8",
                params={"token": pending.playback_token},
            )
            assert failed.status_code == 500
            assert failed.json() == {"detail": "Failed to serve playlist"}
        pending.playlist_path.unlink()
        not_ready = await clients[1].get(
            "/api/live/stream/shared-id/playlist.m3u8",
            params={"token": pending.playback_token},
        )
        assert not_ready.status_code == 503
        assert not_ready.json() == {"detail": "Stream not ready yet, retry shortly"}
        assert (await clients[0].delete("/api/live/stop/shared-id")).status_code == 404
        assert file_threads and get_ident() not in file_threads
    finally:
        for actor in actors:
            await actor.stop()
        for child in children:
            await child.wait()
        for app in applications:
            await _close_application_twitch(app)
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()


@pytest.mark.asyncio
async def test_critical_startup_failure_stops_only_its_live_actor(
    image_applications, monkeypatch
):
    applications, _, _, _ = image_applications
    module = importlib.import_module("app.lifespan")
    service_module = importlib.import_module("app.services.live_streaming_service")
    storage = importlib.import_module("app.bootstrap.storage")
    stopped = []

    class Actor:
        def __init__(self, owner):
            self.owner = owner

        async def stop(self):
            stopped.append(self.owner)

    for index, app in enumerate(applications):
        app.state.live_streaming_service = Actor(index)

    def unavailable(settings):
        raise RuntimeError("fixture failed critical preparation")

    monkeypatch.setattr(module, "setup_logging", lambda settings: None)
    monkeypatch.setattr(storage, "prepare_storage_directories", unavailable)
    monkeypatch.setattr(
        service_module, "live_streaming_service", Actor("foreign-default")
    )
    with pytest.raises(RuntimeError, match="failed critical preparation"):
        async with module.lifespan(applications[0]):
            raise AssertionError("failed preparation must not yield")
    assert stopped == [0]


@pytest.mark.asyncio
async def test_live_start_projects_its_own_streamer_before_async_admission(
    image_applications, monkeypatch
):
    applications, databases, clients, queries = image_applications
    actor = await run_in_thread_pool(
        live_routes.get_live_streaming_service,
        HTTPConnection({"type": "http", "app": applications[0], "headers": []}),
    )
    admitted = []

    async def start():
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)

    async def admit(**values):
        admitted.append(values)
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        return LiveStreamStartResult("fixture-admitted", False)

    monkeypatch.setattr(actor, "start", start)
    monkeypatch.setattr(actor, "start_stream", admit)
    monkeypatch.setattr(
        actor,
        "get_session",
        lambda _: SimpleNamespace(playback_token="fixture-playback"),
    )
    try:
        queries.clear()
        response = await clients[0].post(
            "/api/live/start/OWNER-0", json={"quality": "720p"}
        )
        assert response.status_code == 200
        assert response.json()["streamer_name"] == "owner-0"
        assert admitted == [
            {
                "streamer_name": "owner-0",
                "channel_key": "owner-0",
                "quality": "720p",
                "supported_codecs": "h264",
                "user_id": "1",
                "enhanced_quality": False,
            }
        ]
        reads = [thread for thread, sql in queries if "FROM streamers" in sql]
        assert reads and get_ident() not in reads
        assert (await clients[1].post("/api/live/start/OWNER-0")).status_code == 404
    finally:
        for app in applications:
            own = getattr(app.state, "live_streaming_service", None)
            if own is not None:
                await own.stop()
            await _close_application_twitch(app)
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()
