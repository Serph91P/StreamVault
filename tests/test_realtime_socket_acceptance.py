"""Real loopback HTTP/WebSocket acceptance without the production lifespan.

Uses synthetic SQLite auth, product routers, manager and task tracker. No Twitch,
workers, media jobs, production configuration, or mocked transport is involved.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import importlib
import secrets
import socket
import threading
import time

import httpx
import uvicorn
from websockets.asyncio.client import connect
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import SecretStr


def test_authenticated_socket_producers_queue_replay_and_restart(tmp_path, monkeypatch):
    import app.database as database
    import app.dependencies as dependencies
    import app.middleware.auth as middleware
    from app.config.settings import settings
    from app.database import Base
    from app.models import User, Session, RefreshToken, SystemState, NotificationState
    from app.routes import auth, notifications, realtime, settings as settings_routes

    communication = importlib.import_module(
        "app.services.communication.websocket_manager"
    )
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
    tables = [
        model.__table__
        for model in (User, Session, RefreshToken, SystemState, NotificationState)
    ]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(
        settings, "auth_jwt_secret", SecretStr(secrets.token_urlsafe(48))
    )
    monkeypatch.setattr(settings, "USE_SECURE_COOKIES", False)
    monkeypatch.setattr(middleware, "SessionLocal", factory)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(dependencies, "SessionLocal", factory)
    password = secrets.token_urlsafe(24)
    with factory() as db:
        db.add(
            User(
                username="realtime-admin",
                password=AuthService(db).hash_password(password),
                is_admin=True,
                is_active=True,
            )
        )
        db.add(SystemState(id=1, welcome_completed=True))
        db.commit()

    @contextmanager
    def backend(manager):
        # These are the same imports a fresh backend process resolves.
        monkeypatch.setattr(communication, "websocket_manager", manager)
        monkeypatch.setattr(dependencies, "websocket_manager", manager)
        monkeypatch.setattr(realtime, "websocket_manager", manager)
        app = FastAPI()
        app.include_router(auth.router, prefix="/auth")
        app.include_router(realtime.router)
        app.include_router(settings_routes.router)
        app.include_router(notifications.router)
        app.add_middleware(middleware.AuthMiddleware)
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

            yield f"http://127.0.0.1:{port}", on_backend
        finally:
            if server.started:
                asyncio.run_coroutine_threadsafe(manager.close_all(), loop).result(
                    timeout=5
                )
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            assert not thread.is_alive(), "loopback server did not stop"
            loop.close()

    async def receive(ws, event_type):
        async with asyncio.timeout(5):
            while True:
                event = json.loads(await ws.recv())
                if event["type"] == event_type:
                    return event

    async def exercise(origin, on_backend):
        async with httpx.AsyncClient(
            base_url=origin, headers={"accept": "application/json", "origin": origin}
        ) as client:
            assert (await client.get("/api/realtime/events")).status_code == 401
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
                # Formerly disconnected Recording/Postprocessing import path.
                await on_backend(
                    communication.websocket_manager.send_notification(
                        {"type": "recording.started", "data": {"recording_id": 933}}
                    )
                )
                recording = await receive(ws, "recording.started")
                assert recording["event_id"] > notification["event_id"]

                tracker = TaskProgressTracker(
                    websocket_manager=communication.websocket_manager
                )
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
                communication.websocket_manager.send_notification(
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
                        communication.websocket_manager.send_notification(
                            {"type": "test", "data": {"test_id": f"retention-{index}"}}
                        )
                    )
                replay = (
                    await client.get("/api/realtime/events", params={"since": 0})
                ).json()
                assert replay["gap"] is True
                return generation, replay["latest_event_id"], cookie

    # Use the real canonical singleton first, not an independently injected producer.
    manager = communication.websocket_manager
    assert manager is dependencies.websocket_manager is realtime.websocket_manager
    monkeypatch.setattr(manager, "_event_log_size", 3)
    monkeypatch.setattr(manager, "_next_event_id", 0)
    from collections import deque

    monkeypatch.setattr(manager, "_event_log", deque(maxlen=3))
    with backend(manager) as (origin, on_backend):
        generation, cursor, cookie = asyncio.run(exercise(origin, on_backend))

    # Stop the actual listening server and start a fresh backend/manager against
    # the same synthetic auth DB, as on a process restart (no production lifespan).
    fresh = communication.ConnectionManager(event_log_size=3)
    with backend(fresh) as (origin, on_backend):

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
