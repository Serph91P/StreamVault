"""Real recording persistence operations own complete off-loop transaction scopes."""

import asyncio
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import datetime, timezone
from threading import Barrier, Event, get_ident

import pytest
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.database import Base, DatabaseLifecycle
from app.models import Recording, Stream, Streamer, StreamEvent
from app.services.recording.recording_database_service import RecordingDatabaseService
from app.utils.retry_decorator import NonRetryableError


@pytest.mark.asyncio
async def test_recording_operations_return_closed_values_and_isolate_peer_databases(
    tmp_path,
):
    lifecycles = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    services = []
    threads = []
    sessions = set()
    loop_thread = get_ident()

    def began(session, _transaction, _connection):
        sessions.add(id(session))

    def ended(session, _transaction):
        if not session.in_transaction():
            sessions.discard(id(session))

    try:
        for name, lifecycle in zip(("first", "second"), lifecycles, strict=True):
            with lifecycle.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with lifecycle.sync_session_factory() as session:
                session.add(Streamer(id=1, username=name, twitch_id=name))
                session.commit()
            event.listen(
                lifecycle.sync_engine,
                "before_cursor_execute",
                lambda *_: threads.append(get_ident()),
            )
            services.append(
                RecordingDatabaseService(
                    session_factory=lambda lifecycle=lifecycle: (
                        lifecycle.sync_session_factory()
                    )
                )
            )
        assert threads == []
        event.listen(Session, "after_begin", began)
        event.listen(Session, "after_transaction_end", ended)
        try:
            for name, service in zip(("first", "second"), services, strict=True):
                stream = await service.create_stream(
                    {
                        "streamer_id": 1,
                        "twitch_stream_id": "same-id",
                        "title": name,
                        "category_name": "category",
                        "started_at": datetime.now(timezone.utc),
                    }
                )
                recording = await service.create_recording(stream.id, name + ".ts")
                assert not sessions
                assert (
                    is_dataclass(recording)
                    and inspect(recording, raiseerr=False) is None
                )
                assert (
                    is_dataclass(recording.stream)
                    and inspect(recording.stream, raiseerr=False) is None
                )
                assert {field.name for field in fields(recording)} == set(
                    Recording.__table__.columns.keys()
                ) | {"stream"}
                assert recording.stream.streamer.username == name
                assert inspect(recording.stream.streamer, raiseerr=False) is None
                with pytest.raises(FrozenInstanceError):
                    recording.status = "failed"
                assert (await service.get_recording(recording.id)).id == recording.id
                assert (
                    await service.get_recording_by_id(recording.id)
                ).id == recording.id
                assert (await service.get_stream_by_id(stream.id)).title == name
                assert (await service.get_streamer_by_id(1)).username == name
                assert (
                    await service.get_stream_by_twitch_stream_id("same-id")
                ).id == stream.id
                pair = await service.get_stream_with_streamer(stream.id)
                assert pair[0].id == stream.id and pair[1].username == name
                assert [
                    value.id
                    for value in await service.get_recordings_by_status("recording")
                ] == [recording.id]
                assert [
                    value.id for value in await service.get_active_recordings_from_db()
                ] == [recording.id]
                await service.ensure_initial_stream_events(stream.id)
                await service.ensure_initial_stream_events(stream.id)
                await service.update_recording_path(recording.id, name + ".mp4")
                await service.update_recording_status(
                    recording.id, "completed", duration_seconds=12
                )
                completed = await service.get_recording(recording.id)
                assert completed.path == name + ".mp4" and completed.duration == 12
                assert (
                    completed.status == "completed" and completed.end_time is not None
                )
                await service.ensure_stream_ended(stream.id)
                ended_stream = await service.get_stream_by_id(stream.id)
                assert ended_stream.ended_at is not None and not ended_stream.is_live
                await service.mark_recording_failed(recording.id, "worker failure")
                assert (
                    await service.get_recording(recording.id)
                ).error_message == "worker failure"
                assert await service.get_recording(-1) is None
                assert await service.get_stream_by_id(-1) is None
                assert await service.get_streamer_by_id(-1) is None
                assert await service.get_stream_with_streamer(-1) is None
                assert await service.get_stream_by_twitch_stream_id("missing") is None
                with pytest.raises(NonRetryableError):
                    await service.update_recording_status(-1, "failed")
                with pytest.raises(NonRetryableError):
                    await service.update_recording_path(-1, "missing")
                with pytest.raises(NonRetryableError):
                    await service.mark_recording_failed(-1)
                assert not sessions
            assert threads and loop_thread not in threads
        finally:
            event.remove(Session, "after_begin", began)
            event.remove(Session, "after_transaction_end", ended)
        for name, lifecycle in zip(("first", "second"), lifecycles, strict=True):
            with lifecycle.sync_session_factory() as session:
                assert session.scalar(select(Stream.title)) == name
                assert session.scalar(select(Recording.path)) == name + ".mp4"
                events = session.scalars(
                    select(StreamEvent).order_by(StreamEvent.timestamp)
                ).all()
                assert [value.event_type for value in events] == [
                    "channel.update",
                    "stream.online",
                ]
                assert (events[1].timestamp - events[0].timestamp).total_seconds() == 1
    finally:
        for lifecycle in lifecycles:
            await lifecycle.adispose()


@pytest.mark.asyncio
async def test_recording_failure_rolls_back_before_the_next_operation(tmp_path):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'rollback.db'}")
    try:
        with lifecycle.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(Streamer(id=1, username="owner", twitch_id="owner"))
            session.commit()
        service = RecordingDatabaseService(
            session_factory=lambda: lifecycle.sync_session_factory()
        )
        data = {"streamer_id": 1, "twitch_stream_id": "unique"}
        await service.create_stream(data)
        with pytest.raises(NonRetryableError):
            await service.create_stream(data)
        stream = await service.create_stream(
            {**data, "twitch_stream_id": "after-rollback"}
        )
        assert stream.twitch_stream_id == "after-rollback"
        values = await asyncio.gather(
            service.create_recording(stream.id, "first.ts"),
            service.create_recording(stream.id, "second.ts"),
        )
        assert values[0].id != values[1].id
        assert {
            value.path for value in await service.get_active_recordings_from_db()
        } == {"first.ts", "second.ts"}
    finally:
        await lifecycle.adispose()


@pytest.mark.asyncio
async def test_recording_cancellation_drains_the_owned_transaction(tmp_path):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'cancellation.db'}")
    entered, release = Event(), Event()
    checked_out = set()

    def pause(_connection, _cursor, statement, *_args):
        if statement.startswith("INSERT INTO recordings"):
            entered.set()
            assert release.wait(10), "test did not release the recording worker"

    def checkout(connection, *_args):
        checked_out.add(id(connection))

    def checkin(connection, *_args):
        checked_out.discard(id(connection))

    task = None
    try:
        with lifecycle.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(Streamer(id=1, username="owner", twitch_id="owner"))
            session.add(Stream(id=1, streamer_id=1, twitch_stream_id="stream"))
            session.commit()
        event.listen(lifecycle.sync_engine, "before_cursor_execute", pause)
        event.listen(lifecycle.sync_engine, "checkout", checkout)
        event.listen(lifecycle.sync_engine, "checkin", checkin)
        service = RecordingDatabaseService(
            session_factory=lambda: lifecycle.sync_session_factory()
        )
        task = asyncio.create_task(service.create_recording(1, "capture.ts"))
        assert await asyncio.to_thread(entered.wait, 10)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and checked_out
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not checked_out
        # Cancellation cannot undo a completed driver commit; it must drain ownership.
        assert [
            value.path for value in await service.get_active_recordings_from_db()
        ] == ["capture.ts"]
        assert not checked_out
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await lifecycle.adispose()


@pytest.mark.asyncio
async def test_concurrent_initial_event_writers_keep_one_timeline(tmp_path):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'timeline.db'}")
    try:
        with lifecycle.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(Streamer(id=1, username="owner", twitch_id="owner"))
            session.add(
                Stream(
                    id=1,
                    streamer_id=1,
                    twitch_stream_id="stream",
                    category_name="category",
                )
            )
            session.commit()
        simultaneous = Barrier(2)

        def sessions():
            simultaneous.wait(timeout=10)
            return lifecycle.sync_session_factory()

        service = RecordingDatabaseService(session_factory=sessions)
        await asyncio.gather(
            *(service.ensure_initial_stream_events(1) for _ in range(2))
        )
        with lifecycle.sync_session_factory() as session:
            values = session.scalars(
                select(StreamEvent).order_by(StreamEvent.timestamp)
            ).all()
            assert [value.event_type for value in values] == [
                "channel.update",
                "stream.online",
            ]
    finally:
        await lifecycle.adispose()
