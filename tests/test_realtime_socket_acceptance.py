"""Real loopback HTTP/WebSocket acceptance without the production lifespan.

Uses synthetic SQLite auth, product routers, manager and task tracker. No Twitch,
workers, media jobs, production configuration, or mocked transport is involved.
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
import json

import secrets
import socket
import threading
import time

from unittest.mock import AsyncMock

import httpx
import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError
from starlette.requests import HTTPConnection
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import SecretStr


def test_authenticated_socket_producers_queue_replay_and_restart(tmp_path, monkeypatch):
    import app.dependencies as dependencies
    from app.config.settings import settings
    from app.database import Base
    from app.main import create_app
    from app.models import User, SystemState, GlobalSettings, Streamer
    from app.lifespan import (
        _close_application_twitch,
        _close_application_images,
        _close_application_proxy,
    )
    from app.utils.async_db_utils import run_in_thread_pool
    from app.services.core.auth_service import AuthService
    from app.services.queues.task_progress_tracker import (
        QueueTask,
        TaskPriority,
        TaskProgressTracker,
        TaskStatus,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runtime_settings = settings.model_copy(
        update={
            "auth_jwt_secret": SecretStr(secrets.token_urlsafe(48)),
            "USE_SECURE_COOKIES": False,
            "database_url": SecretStr(f"sqlite:///{tmp_path / 'auth.sqlite'}"),
            "RECORDING_DIRECTORY": str(tmp_path / "recordings"),
        }
    )
    recorder = AsyncMock()
    password = secrets.token_urlsafe(24)
    with factory() as db:
        db.add(
            User(
                username="realtime-admin",
                password=AuthService(db, settings=runtime_settings).hash_password(
                    password
                ),
                is_admin=True,
                is_active=True,
            )
        )
        db.add(SystemState(id=1, welcome_completed=True))
        db.add(GlobalSettings(id=1, notifications_enabled=False))
        db.add(
            Streamer(
                id=1034,
                twitch_id="synthetic-alert-off",
                username="synthetic-alert-off",
                is_live=False,
                title="Old title",
                category_name="Old category",
            )
        )
        db.commit()

    @contextmanager
    def backend():
        app = create_app(settings=runtime_settings)
        app.dependency_overrides[dependencies.get_recording_manager] = lambda: recorder
        manager = app.state.websocket_manager
        assert (
            dependencies.get_websocket_manager(
                HTTPConnection({"type": "http", "app": app})
            )
            is manager
        )
        manager._event_log_size = 3
        manager._event_log = deque(maxlen=3)
        loop = asyncio.new_event_loop()
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))

        def run():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(server.serve(sockets=[sock]))

        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.monotonic() + 10
        try:
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline, (
                    "loopback server failed to start"
                )
                time.sleep(0.01)

            async def on_backend(coro):
                return await asyncio.wrap_future(
                    asyncio.run_coroutine_threadsafe(coro, loop)
                )

            yield f"http://127.0.0.1:{port}", on_backend, app
        finally:
            if server.started:

                async def close_app():
                    await manager.close_all()
                    await _close_application_images(app)
                    await _close_application_twitch(app)
                    await _close_application_proxy(app)
                    await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()

                asyncio.run_coroutine_threadsafe(close_app(), loop).result(timeout=5)
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            assert not thread.is_alive(), "loopback server did not stop"
            loop.run_until_complete(app.state.database_lifecycle.adispose())
            loop.close()

    async def receive(ws, event_type):
        async with asyncio.timeout(5):
            while True:
                event = json.loads(await ws.recv())
                if event["type"] == event_type:
                    return event

    async def exercise(origin, on_backend, app):
        manager = app.state.websocket_manager
        async with httpx.AsyncClient(
            base_url=origin, headers={"accept": "application/json", "origin": origin}
        ) as client:
            assert (await client.get("/api/realtime/events")).status_code == 401
            async with connect(origin.replace("http:", "ws:") + "/ws") as anonymous:
                with pytest.raises(ConnectionClosedError) as rejected:
                    await asyncio.wait_for(anonymous.recv(), 5)
                assert rejected.value.rcvd.code == 4001
            login = await client.post(
                "/auth/login", json={"username": "realtime-admin", "password": password}
            )
            assert login.status_code == 200
            assert (await client.get("/auth/check")).status_code == 200
            cookie = "; ".join(
                f"{key}={value}" for key, value in client.cookies.items()
            )
            async with connect(
                origin.replace("http:", "ws:") + "/ws",
                additional_headers={"Cookie": cookie},
            ) as ws:
                status = await receive(ws, "connection.status")
                generation = status["data"]["generation"]
                response = await client.post(
                    "/api/settings/test-websocket-notification"
                )
                assert response.status_code == 200
                notification = await receive(ws, "channel.update")
                assert (
                    notification["data"]["test_id"]
                    == response.json()["notification_id"]
                )
                # Producers and real HTTP/WS adapters share this app's manager.
                await on_backend(
                    manager.send_notification(
                        {"type": "recording.started", "data": {"recording_id": 933}}
                    )
                )
                recording = await receive(ws, "recording.started")
                assert recording["event_id"] > notification["event_id"]

                # Real registered handler -> dispatcher -> authenticated socket, alerts off.
                registry = await on_backend(
                    run_in_thread_pool(
                        dependencies._get_application_event_registry, app
                    )
                )
                registry.get_user_info = AsyncMock(return_value=None)
                previous_id = recording["event_id"]
                for wire_type, is_live in (
                    ("stream.online", True),
                    ("channel.update", True),
                    ("stream.offline", False),
                ):
                    await on_backend(
                        registry.handlers[wire_type](
                            {
                                "id": "synthetic-stream-1034",
                                "broadcaster_user_id": "synthetic-alert-off",
                                "broadcaster_user_name": "synthetic-alert-off",
                                "broadcaster_user_login": "synthetic-alert-off",
                                "started_at": "2026-01-01T00:00:00Z",
                                "title": "New title",
                                "category_name": "New category",
                                "language": "de",
                            },
                        )
                    )
                    event = await receive(ws, wire_type)
                    assert event["event_id"] == previous_id + 1
                    previous_id = event["event_id"]
                    assert event["data"]["streamer_id"] == 1034
                    assert event["data"]["is_live"] is is_live
                    if wire_type == "channel.update":
                        assert event["data"]["title"] == "New title"
                        assert event["data"]["category_name"] == "New category"
                    with factory() as db:
                        streamer = db.get(Streamer, 1034)
                        assert streamer.is_live is is_live
                        if wire_type != "stream.online":
                            assert streamer.title == "New title"
                            assert streamer.category_name == "New category"
                recorder.start_recording.assert_not_awaited()

                tracker = TaskProgressTracker(websocket_manager=manager)
                task = QueueTask(
                    id="synthetic-933",
                    task_type="acceptance",
                    priority=TaskPriority.NORMAL,
                    payload={"streamer_name": "Synthetic"},
                    status=TaskStatus.PENDING,
                    created_at=datetime.now(timezone.utc),
                )

                async def change(status=None, progress=None):
                    if status is not None:
                        tracker.update_task_status(task.id, status)
                    if progress is not None:
                        tracker.update_task_progress(task.id, progress)
                    if tracker.background_tasks:
                        await asyncio.gather(*list(tracker.background_tasks))

                tracker.add_task(task)
                await on_backend(change(status=TaskStatus.RUNNING))
                assert (await receive(ws, "task_status_update"))["data"][
                    "status"
                ] == "running"
                await on_backend(change(progress=45))
                assert (await receive(ws, "task_progress_update"))["data"][
                    "progress"
                ] == 45
                await on_backend(change(status=TaskStatus.COMPLETED))
                assert (await receive(ws, "task_status_update"))["data"][
                    "status"
                ] == "completed"
                cursor = (await client.get("/api/realtime/events")).json()[
                    "latest_event_id"
                ]

            # Event produced with no connected browser, then retrieved by real HTTP replay.
            await on_backend(
                manager.send_notification(
                    {"type": "test", "data": {"test_id": "offline"}}
                )
            )
            async with connect(
                origin.replace("http:", "ws:") + "/ws",
                additional_headers={"Cookie": cookie},
            ) as ws:
                await receive(ws, "connection.status")
                replay = (
                    await client.get(
                        "/api/realtime/events",
                        params={"since": cursor, "generation": generation},
                    )
                ).json()
                assert replay["reset"] is False
                assert [event["data"]["test_id"] for event in replay["events"]] == [
                    "offline"
                ]
                # Force retention overflow using only synthetic local events.
                for index in range(4):
                    await on_backend(
                        manager.send_notification(
                            {"type": "test", "data": {"test_id": f"retention-{index}"}}
                        )
                    )
                replay = (
                    await client.get("/api/realtime/events", params={"since": 0})
                ).json()
                assert replay["gap"] is True
                return generation, replay["latest_event_id"], cookie

    with backend() as (origin, on_backend, app):
        manager = app.state.websocket_manager
        generation, cursor, cookie = asyncio.run(exercise(origin, on_backend, app))

    # Stop the actual listening server and start a fresh backend/manager against
    # the same synthetic auth DB, as on a process restart (no production lifespan).
    with backend() as (origin, on_backend, app):
        fresh = app.state.websocket_manager
        assert fresh is not manager

        async def after_restart():
            await on_backend(
                fresh.send_notification(
                    {"type": "test", "data": {"test_id": "after-restart"}}
                )
            )
            async with httpx.AsyncClient(
                base_url=origin,
                headers={"Cookie": cookie, "accept": "application/json"},
            ) as client:
                response = await client.get(
                    "/api/realtime/events",
                    params={"since": cursor, "generation": generation},
                )
                assert response.status_code == 200
                replay = response.json()
                assert replay["reset"] is True and replay["generation"] != generation
                assert [event["data"]["test_id"] for event in replay["events"]] == [
                    "after-restart"
                ]
            async with connect(
                origin.replace("http:", "ws:") + "/ws",
                additional_headers={"Cookie": cookie},
            ) as ws:
                await receive(ws, "connection.status")
                await on_backend(
                    fresh.send_notification(
                        {"type": "test", "data": {"test_id": "live-after-restart"}}
                    )
                )
                assert (await receive(ws, "test"))["event_id"] == 2

        asyncio.run(after_restart())
    engine.dispose()
