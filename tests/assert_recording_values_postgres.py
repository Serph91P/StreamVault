"""Opt-in real PostgreSQL probe; owns only random temporary schemas."""

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, get_ident
from uuid import uuid4

from sqlalchemy import create_engine, event, inspect, select, update, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config.settings import Settings
from app.database import Base
from app.models import (
    Stream,
    Recording,
    RecordingSettings,
    Streamer,
    StreamerRecordingSettings,
    StreamEvent,
    RecordingProcessingState,
    StreamMetadata,
)
from app.services.communication.websocket_manager import ConnectionManager
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)
from app.services.recording.config_manager import ConfigManager
from app.services.recording.recording_database_service import RecordingDatabaseService
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.retry_decorator import NonRetryableError


async def check_concurrent_timeline(engine, sessions, service, schema):
    stream = await service.create_stream(
        {
            "streamer_id": 1,
            "twitch_stream_id": "concurrent",
            "category_name": "category",
        }
    )
    locked, release = Event(), Event()
    timeline_reads = []

    def observe(_connection, _cursor, statement, *_args):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and schema + ".stream_events" in statement
        ):
            timeline_reads.append(statement)

    def hold_row():
        with sessions() as session, session.begin():
            assert (
                session.scalar(
                    select(Stream.id).where(Stream.id == stream.id).with_for_update()
                )
                == stream.id
            )
            locked.set()
            assert release.wait(15), "test did not release the row lock"

    def blocked_writers():
        with engine.connect() as connection:
            return connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND query LIKE :pattern"
                ),
                {"pattern": "%" + schema + "%"},
            )

    event.listen(engine, "before_cursor_execute", observe)
    lock_task = asyncio.create_task(run_in_thread_pool(hold_row))
    writers = []
    try:
        assert await asyncio.to_thread(locked.wait, 10)
        writers = [
            asyncio.create_task(service.ensure_initial_stream_events(stream.id))
            for _ in range(2)
        ]
        deadline = asyncio.get_running_loop().time() + 10
        while await run_in_thread_pool(blocked_writers) < 2:
            assert asyncio.get_running_loop().time() < deadline, (
                "both writers must reach the real DB lock"
            )
            await asyncio.sleep(0.01)
        assert not timeline_reads, (
            "timeline checks must wait for ownership of the stream row"
        )
    finally:
        release.set()
        await asyncio.gather(lock_task, *writers, return_exceptions=True)
        event.remove(engine, "before_cursor_execute", observe)
    await asyncio.gather(*writers)

    def read_types():
        with sessions() as session:
            return list(
                session.scalars(
                    select(StreamEvent.event_type)
                    .where(StreamEvent.stream_id == stream.id)
                    .order_by(StreamEvent.timestamp)
                )
            )

    assert await run_in_thread_pool(read_types) == ["channel.update", "stream.online"]


async def check_processing_context(
    engine, sessions, schema, stream_id, recording_id, label
):
    manager = ConnectionManager()
    handlers = PostProcessingTaskHandlers(
        session_factory=sessions, connection_manager=manager
    )
    locked, release = Event(), Event()
    state_reads = []

    def observe(_connection, _cursor, statement, *_):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and schema + ".recording_processing_state" in statement
        ):
            state_reads.append(statement)

    def hold_row():
        with sessions() as session, session.begin():
            assert (
                session.scalar(
                    select(Recording.id)
                    .where(Recording.id == recording_id)
                    .with_for_update()
                )
                == recording_id
            )
            locked.set()
            assert release.wait(15), "test did not release the recording row"

    def blocked_writers():
        with engine.connect() as connection:
            return connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND query LIKE :pattern"
                ),
                {"pattern": "%" + schema + "%"},
            )

    def read_status():
        with sessions() as session:
            state = session.scalar(
                select(RecordingProcessingState).where(
                    RecordingProcessingState.recording_id == recording_id
                )
            )
            return state.metadata_status, state.chapters_status

    event.listen(engine, "before_cursor_execute", observe)
    lock_task = asyncio.create_task(run_in_thread_pool(hold_row))
    writers = []
    try:
        try:
            assert await asyncio.to_thread(locked.wait, 10)
            writers = [
                asyncio.create_task(
                    handlers._record_status(recording_id, stream_id, step, "completed")
                )
                for step in ("metadata", "chapters")
            ]
            deadline = asyncio.get_running_loop().time() + 10
            while await run_in_thread_pool(blocked_writers) < 2:
                assert asyncio.get_running_loop().time() < deadline, (
                    "both status writers must reach the real recording lock"
                )
                await asyncio.sleep(0.01)
            assert not state_reads, (
                "state reads must wait for ownership of the recording row"
            )
        finally:
            release.set()
            await asyncio.gather(lock_task, *writers, return_exceptions=True)
            event.remove(engine, "before_cursor_execute", observe)
        await asyncio.gather(*writers)
        assert await run_in_thread_pool(read_status) == ("completed", "completed")
        with TemporaryDirectory(prefix="processing-boundary-") as directory:
            target = Path(directory) / label / "episode.mp4"
            target.parent.mkdir()

            def seed_metadata():
                with sessions.begin() as session:
                    session.add(StreamMetadata(stream_id=stream_id))

            await run_in_thread_pool(seed_metadata)
            paths = await handlers.metadata_service.ensure_all_chapter_formats(
                stream_id, str(target)
            )
            assert paths and set(paths) == {"vtt", "srt", "ffmpeg", "xml"}
            assert all(Path(filename).is_file() for filename in paths.values())
            assert "artist=" + label in Path(paths["ffmpeg"]).read_text()
            assert "title=" + label in Path(paths["ffmpeg"]).read_text()

            def read_paths():
                with sessions() as session:
                    value = session.scalar(
                        select(StreamMetadata).where(
                            StreamMetadata.stream_id == stream_id
                        )
                    )
                    return (
                        value.chapters_vtt_path,
                        value.chapters_srt_path,
                        value.chapters_ffmpeg_path,
                        value.chapters_xml_path,
                    )

            assert await run_in_thread_pool(read_paths) == tuple(
                paths[key] for key in ("vtt", "srt", "ffmpeg", "xml")
            )
    finally:
        await handlers.cleanup()
        await manager.close_all()


async def main() -> None:
    engine = create_engine(os.environ["STREAMVAULT_POSTGRES_TEST_URL"])
    assert engine.dialect.name == "postgresql"
    schemas = []
    services = []
    factories = []
    configs = []
    sql_threads = []
    checked_out = set()
    loop_thread = get_ident()

    def checkout(connection, *_):
        checked_out.add(id(connection))

    def checkin(connection, *_):
        checked_out.discard(id(connection))

    try:
        for label in ("first", "second"):
            schema = "recording_boundary_" + uuid4().hex
            with engine.begin() as connection:
                connection.execute(CreateSchema(schema))
            schemas.append(schema)
            target = engine.execution_options(schema_translate_map={None: schema})
            Base.metadata.create_all(target)
            sessions = sessionmaker(bind=target)
            factories.append(sessions)
            with sessions.begin() as session:
                session.add(Streamer(id=1, username=label, twitch_id=label))
                session.add(
                    RecordingSettings(id=1, default_quality=label, enabled=True)
                )
                session.add(StreamerRecordingSettings(streamer_id=1, enabled=True))
                session.flush()
                session.execute(update(StreamerRecordingSettings).values(quality=None))
            services.append(RecordingDatabaseService(session_factory=sessions))
            configs.append(
                ConfigManager(
                    session_factory=sessions,
                    settings=Settings(
                        _env_file=None,
                        ENVIRONMENT="test",
                        RECORDING_DIRECTORY="/synthetic/" + label,
                    ),
                )
            )
        event.listen(
            engine, "before_cursor_execute", lambda *_: sql_threads.append(get_ident())
        )
        event.listen(engine, "checkout", checkout)
        event.listen(engine, "checkin", checkin)
        for label, service, config, sessions, schema in zip(
            ("first", "second"), services, configs, factories, schemas, strict=True
        ):
            stream = await service.create_stream(
                {
                    "streamer_id": 1,
                    "twitch_stream_id": "same-id",
                    "title": label,
                    "category_name": "category",
                }
            )
            recording = await service.create_recording(stream.id, label + ".ts")
            assert recording.start_time.tzinfo is not None
            assert inspect(recording, raiseerr=False) is None
            assert inspect(recording.stream, raiseerr=False) is None
            assert inspect(recording.stream.streamer, raiseerr=False) is None
            assert recording.stream.streamer.username == label
            assert await run_in_thread_pool(config.get_quality_setting, 1) == label
            assert config.get_recordings_directory() == "/synthetic/" + label
            assert [
                value.id for value in await service.get_active_recordings_from_db()
            ] == [recording.id]
            await service.ensure_initial_stream_events(stream.id)
            await service.ensure_initial_stream_events(stream.id)
            await check_concurrent_timeline(engine, sessions, service, schema)
            await check_processing_context(
                engine, sessions, schema, stream.id, recording.id, label
            )
            with_error = {"streamer_id": 1, "twitch_stream_id": "same-id"}
            try:
                await service.create_stream(with_error)
            except NonRetryableError:
                pass
            else:
                raise AssertionError(
                    "duplicate Twitch stream must fail without retries"
                )
            failed_id = await service.mark_active_stream_recording_failed(
                stream.id, "synthetic child failure", "streamlink_crash"
            )
            assert failed_id == recording.id
            failed = await service.get_recording(recording.id)
            assert (
                failed.status == "failed"
                and failed.error_message == "synthetic child failure"
            )
            assert failed.failure_reason == "streamlink_crash"
            assert (
                failed.failure_timestamp.tzinfo is not None
                and failed.end_time.tzinfo is not None
            )
            assert (
                await service.mark_active_stream_recording_failed(
                    stream.id, "later", "later"
                )
                is None
            )
            assert await service.get_recording(recording.id) == failed
            assert (
                await service.mark_active_stream_recording_failed(
                    999999, "absent", "absent"
                )
                is None
            )
            await service.update_recording_status(
                recording.id, "completed", path=label + ".mp4", duration_seconds=7
            )
            value = await service.get_recording_by_id(recording.id)
            assert (
                value.status == "completed"
                and value.path == label + ".mp4"
                and value.duration == 7
            )
            await service.ensure_stream_ended(stream.id)
            assert not (await service.get_stream_by_id(stream.id)).is_live
            await service.mark_recording_failed(recording.id, "synthetic failure")
            assert (
                await service.get_recording(recording.id)
            ).error_message == "synthetic failure"
            assert not checked_out
        assert sql_threads and loop_thread not in sql_threads
        for label, sessions in zip(("first", "second"), factories, strict=True):
            with sessions() as session:
                assert session.scalar(select(Recording.path)) == label + ".mp4"
                events = session.scalars(
                    select(StreamEvent)
                    .where(
                        StreamEvent.stream_id
                        == session.scalar(select(Recording.stream_id))
                    )
                    .order_by(StreamEvent.timestamp)
                ).all()
                assert [row.event_type for row in events] == [
                    "channel.update",
                    "stream.online",
                ]
        print(
            "PASS: PostgreSQL recording/config peer isolation, frozen values, off-loop SQL, checked-in scopes, rollback, timelines, serialized processing status and four persisted chapter formats"
        )
    finally:
        for schema in reversed(schemas):
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
