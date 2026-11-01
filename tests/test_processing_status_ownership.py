"""Processing-status persistence and delayed socket delivery belong to one handler."""

import asyncio
import json
from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event, select
from starlette.websockets import WebSocket

from app.database import Base, DatabaseLifecycle
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.services.communication.websocket_manager import ConnectionManager
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)


@pytest.mark.asyncio
async def test_status_updates_are_closed_off_loop_and_cleanup_does_not_cancel_peer(
    tmp_path,
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    handlers = []

    outgoing = [asyncio.Queue(), asyncio.Queue()]
    checked_out = set()
    query_threads = []
    closed_at_send = []
    blocked_send = asyncio.Event()
    release_send = asyncio.Event()
    loop_thread = get_ident()

    def checkout(connection, *_):
        checked_out.add(id(connection))

    def checkin(connection, *_):
        checked_out.discard(id(connection))

    async def receive():
        return {"type": "websocket.connect"}

    class GatedManager(ConnectionManager):
        async def send_notification(self, message):
            if message["type"] == "recording_processing_status":
                closed_at_send.append(not checked_out)
                assert get_ident() == loop_thread
                if self is managers[0]:
                    blocked_send.set()
                    await release_send.wait()
            await super().send_notification(message)

    # Backpressure before transport acceptance, not an undo of already queued frames.
    managers = [GatedManager(), GatedManager()]

    try:
        for index, database in enumerate(databases):
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(
                    Streamer(id=index + 1, username=str(index), twitch_id=str(index))
                )
                session.flush()
                session.add(Stream(id=1, streamer_id=index + 1))
                session.flush()
                session.add(
                    Recording(
                        id=1,
                        stream_id=1,
                        status="recording",
                        start_time=datetime.now(timezone.utc),
                    )
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: query_threads.append(get_ident()),
            )
            event.listen(database.sync_engine, "checkout", checkout)
            event.listen(database.sync_engine, "checkin", checkin)
            handlers.append(
                PostProcessingTaskHandlers(
                    session_factory=lambda database=database: (
                        database.sync_session_factory()
                    ),
                    connection_manager=managers[index],
                )
            )

            async def send(message, index=index):
                await outgoing[index].put(message)

            socket = WebSocket(
                {"type": "websocket", "headers": [], "client": ("127.0.0.1", 12345)},
                receive,
                send,
            )
            assert await managers[index].connect(socket)
        assert query_threads == []
        await handlers[0]._record_status(1, 1, "mp4_remux", "completed")
        await asyncio.wait_for(blocked_send.wait(), 3)
        await handlers[1]._record_status(1, 1, "mp4_remux", "failed", "peer failure")
        await handlers[0].cleanup()

        async def read_status(queue):
            while True:
                message = await asyncio.wait_for(queue.get(), 3)
                if message["type"] == "websocket.send":
                    frame = json.loads(message["text"])
                    if frame["type"] == "recording_processing_status":
                        return frame

        peer = await read_status(outgoing[1])
        assert peer["data"]["streamer_id"] == 2
        assert peer["data"]["statuses"]["mp4_remux"] == "failed"
        assert peer["data"]["last_error"] == "peer failure"
        assert query_threads and loop_thread not in query_threads
        assert closed_at_send == [True, True]
        assert not checked_out
        while not outgoing[0].empty():
            message = outgoing[0].get_nowait()
            if message["type"] == "websocket.send":
                assert (
                    json.loads(message["text"])["type"] != "recording_processing_status"
                )
        for database, status in zip(databases, ("completed", "failed"), strict=True):
            with database.sync_session_factory() as session:
                assert (
                    session.scalar(select(RecordingProcessingState.mp4_remux_status))
                    == status
                )
    finally:
        release_send.set()
        for handler in handlers:
            await handler.cleanup()
        for manager in managers:
            await manager.close_all()
        for database in databases:
            await database.adispose()
