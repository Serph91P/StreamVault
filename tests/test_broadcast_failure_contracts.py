"""Native queue cleanup and realtime fallback/error contracts, not mock payloads."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import sys

import pytest
from sqlalchemy import event
from starlette.websockets import WebSocket

from app.database import Base, DatabaseLifecycle
from app.main import create_app


class ReceivedFrames(list):
    def __init__(self):
        super().__init__()
        self.arrivals = asyncio.Queue()

    async def expect(self, kind):
        async def matching():
            while True:
                for frame in self:
                    if frame["type"] == kind:
                        return frame
                await self.arrivals.get()

        return await asyncio.wait_for(matching(), 3)


@pytest.fixture
async def broadcaster_context(tmp_path):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'broadcast.db'}")
    with database.sync_engine.begin() as connection:
        Base.metadata.create_all(connection)
    app = create_app(database=database)
    outgoing = ReceivedFrames()

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        if message["type"] == "websocket.send":
            frame = json.loads(message["text"])
            outgoing.append(frame)
            outgoing.arrivals.put_nowait(frame)

    socket = WebSocket(
        {"type": "websocket", "headers": [], "client": ("127.0.0.1", 12345)},
        receive,
        send,
    )
    assert await app.state.websocket_manager.connect(socket)
    await outgoing.expect("connection.status")
    outgoing.clear()
    try:
        yield (
            app.state.websocket_broadcast_task,
            app.state.background_queue_service,
            database,
            outgoing,
        )
    finally:
        await app.state.websocket_broadcast_task.stop()
        await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()
        await app.state.background_queue_service.stop()
        await app.state.websocket_manager.close_all()
        await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("capture_exists", [False, True])
async def test_periodic_cleanup_respects_actual_capture_liveness_and_rebroadcasts(
    broadcaster_context, capture_exists
):
    producer, queue, database, frames = broadcaster_context
    child = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time;time.sleep(30)"
    )
    try:
        if not capture_exists:
            child.terminate()
            await child.wait()

        async def capture_checker(recording_id):
            assert recording_id == 1
            return child.returncode is None

        queue.capture_checker = capture_checker
        queue.add_external_task("recording_1", "recording", {"streamer_name": "owned"})
        task = queue.external_tasks["recording_1"]
        task.started_at = datetime.now(timezone.utc) - timedelta(days=1)
        await queue.queue_manager.progress_tracker.cleanup_background_tasks()
        frames.clear()
        await producer._auto_cleanup_stuck_tasks()
        status = task.status.value
        assert status == ("running" if capture_exists else "failed")
        if not capture_exists:
            assert task.completed_at is not None
            assert "recovery required" in task.error_message
            await frames.expect("background_queue_update")
            await frames.expect("active_recordings_update")
            assert any(frame["type"] == "background_queue_update" for frame in frames)
            assert any(
                frame["type"] == "active_recordings_update" and frame["data"] == []
                for frame in frames
            )
            before = len(
                [
                    frame
                    for frame in frames
                    if frame["type"] == "active_recordings_update"
                ]
            )
            await producer._auto_cleanup_stuck_tasks()
            await producer._broadcast_active_recordings()
            assert (
                len(
                    [
                        frame
                        for frame in frames
                        if frame["type"] == "active_recordings_update"
                    ]
                )
                == before
            )
        else:
            assert not frames
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        if child.returncode is None:
            child.terminate()
            await child.wait()


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [AttributeError, RuntimeError])
async def test_queue_snapshot_failure_does_not_publish_invented_status(
    broadcaster_context, monkeypatch, caplog, error_type
):
    producer, queue, _, frames = broadcaster_context

    def unavailable():
        raise error_type("synthetic unavailable queue snapshot")

    with monkeypatch.context() as patch:
        patch.setattr(queue, "get_queue_statistics", unavailable)
        await producer._broadcast_background_queue_status()
    assert not frames and producer._last_queue_hash is None
    assert "synthetic unavailable queue snapshot" in caplog.text
    await producer._broadcast_background_queue_status()
    await frames.expect("background_queue_update")
    assert len(frames) == 1 and frames[0]["type"] == "background_queue_update"


@pytest.mark.asyncio
async def test_failed_active_snapshot_can_retry_without_publishing_or_leaking(
    broadcaster_context,
):
    producer, _, database, frames = broadcaster_context

    def unavailable(*_args):
        raise OSError("synthetic unavailable active catalog")

    event.listen(database.sync_engine, "before_cursor_execute", unavailable)
    try:
        await producer._broadcast_active_recordings()
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", unavailable)
    assert not frames and producer._last_recordings_hash is None
    assert database.sync_engine.pool.checkedout() == 0
    await producer._broadcast_active_recordings()
    await frames.expect("active_recordings_update")
    assert frames[-1]["type"] == "active_recordings_update" and frames[-1]["data"] == []
    await producer._broadcast_active_recordings()
    assert len(frames) == 1


@pytest.mark.asyncio
async def test_repeated_start_keeps_one_owned_periodic_task(broadcaster_context):
    producer, _, _, _ = broadcaster_context
    await producer.start()
    original = producer._task
    await producer.start()
    assert producer._task is original and producer.is_running
    await producer.stop()
    assert original.done() and not producer.is_running


@pytest.mark.parametrize("kind", ["none", "naive", "aware", "offset"])
def test_duration_fallback_is_nonnegative_and_safe(kind):
    from app.tasks.websocket_broadcast_task import WebSocketBroadcastTask

    producer = WebSocketBroadcastTask()
    if kind == "none":
        assert producer._calculate_duration(None) == 0
        return
    start = datetime.now(timezone.utc) - timedelta(seconds=10)
    if kind == "naive":
        start = start.replace(tzinfo=None)
    elif kind == "offset":
        start = start.astimezone(timezone(timedelta(hours=2)))
    now = datetime.utcnow() if start.tzinfo is None else datetime.now(timezone.utc)
    before = int((now - start).total_seconds())
    result = producer._calculate_duration(start)
    now = datetime.utcnow() if start.tzinfo is None else datetime.now(timezone.utc)
    assert before <= result <= int((now - start).total_seconds())


@pytest.mark.asyncio
async def test_empty_connection_set_skips_delivery_and_deduplicates_snapshots(
    broadcaster_context,
):
    producer, _, database, frames = broadcaster_context
    await producer.connection_manager.close_all()
    await producer._broadcast_active_recordings()
    await producer._broadcast_background_queue_status()
    hashes = producer._last_recordings_hash, producer._last_queue_hash
    assert all(hashes) and not frames
    await producer._broadcast_active_recordings()
    await producer._broadcast_background_queue_status()
    assert (producer._last_recordings_hash, producer._last_queue_hash) == hashes
    assert not frames and database.sync_engine.pool.checkedout() == 0
