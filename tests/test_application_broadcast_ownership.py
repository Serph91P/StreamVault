"""Periodic realtime producers snapshot only their own DB/queue off-loop."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import threading

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket

from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.models import Recording, Stream, Streamer


@pytest.mark.asyncio
async def test_factory_broadcaster_uses_owned_db_queue_and_closed_session_snapshots(
    tmp_path: Path,
) -> None:
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("broadcast-first", "broadcast-second")
    ]
    apps = [create_app(database=database) for database in databases]
    assert all(hasattr(app.state, "websocket_broadcast_task") for app in apps)
    loop_thread = threading.get_ident()
    sql_threads = []
    active_sessions = set()
    closed_at_send = []
    frames = [asyncio.Queue(), asyncio.Queue()]
    task_ids = []

    def transaction_open(session, *_args):
        active_sessions.add(id(session))

    def transaction_closed(session, *_args):
        active_sessions.discard(id(session))

    def query_thread(*_args):
        sql_threads.append(threading.get_ident())

    for database, label in zip(databases, ("first", "second"), strict=True):
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as db:
            db.add(Streamer(id=1, twitch_id=label, username=label))
            db.flush()
            db.add(Stream(id=1, streamer_id=1, title=label))
            db.flush()
            db.add(
                Recording(
                    id=1,
                    stream_id=1,
                    start_time=datetime.now(timezone.utc),
                    status="recording",
                    path=f"/{label}.ts",
                )
            )
            db.commit()
        event.listen(database.sync_engine, "before_cursor_execute", query_thread)
    event.listen(Session, "after_begin", transaction_open)
    event.listen(Session, "after_transaction_end", transaction_closed)

    try:
        for app, outgoing in zip(apps, frames, strict=True):
            queue = app.state.background_queue_service
            task_ids.append(
                await queue.enqueue_task("scope.probe", {"streamer_name": "scope"})
            )
            await queue.queue_manager.progress_tracker.cleanup_background_tasks()

            async def receive():
                return {"type": "websocket.connect"}

            async def send(message, outgoing=outgoing):
                if message["type"] == "websocket.send":
                    data = json.loads(message["text"])
                    if data["type"] == "active_recordings_update":
                        closed_at_send.append(not active_sessions)
                await outgoing.put(message)

            socket = WebSocket(
                {"type": "websocket", "headers": [], "client": ("127.0.0.1", 12345)},
                receive,
                send,
            )
            assert await app.state.websocket_manager.connect(socket)
            assert (await outgoing.get())["type"] == "websocket.accept"
            await asyncio.wait_for(outgoing.get(), 3)
        for app, outgoing, label, task_id in zip(
            apps, frames, ("first", "second"), task_ids, strict=True
        ):
            producer = app.state.websocket_broadcast_task
            await producer._broadcast_active_recordings()
            message = json.loads((await asyncio.wait_for(outgoing.get(), 3))["text"])
            assert message["type"] == "active_recordings_update"
            assert [row["streamer_name"] for row in message["data"]] == [label]
            assert [row["file_path"] for row in message["data"]] == [f"/{label}.ts"]
            await producer._broadcast_background_queue_status()
            message = json.loads((await asyncio.wait_for(outgoing.get(), 3))["text"])
            assert message["type"] == "background_queue_update"
            assert [task["id"] for task in message["data"]["active_tasks"]] == [task_id]
        assert sql_threads and all(thread != loop_thread for thread in sql_threads)
        assert closed_at_send == [True, True]
        await apps[0].state.websocket_broadcast_task.start()
        await apps[1].state.websocket_broadcast_task.start()
        await apps[0].state.websocket_broadcast_task.stop()
        assert apps[1].state.websocket_broadcast_task.is_running
    finally:
        event.remove(Session, "after_begin", transaction_open)
        event.remove(Session, "after_transaction_end", transaction_closed)
        for app, database in zip(apps, databases, strict=True):
            await app.state.websocket_broadcast_task.stop()
            await app.state.websocket_manager.close_all()
            await app.state.background_queue_service.stop()
            await database.adispose()
