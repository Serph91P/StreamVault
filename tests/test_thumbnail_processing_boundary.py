"""Native queued thumbnail extraction keeps data and disk I/O with its owner."""

import os
import subprocess
from datetime import datetime, timezone
from threading import get_ident

import pytest
from PIL import Image
from sqlalchemy import event, select

from app.database import Base, DatabaseLifecycle
from app.models import (
    Recording,
    RecordingProcessingState,
    Stream,
    Streamer,
    StreamMetadata,
)
from app.services.communication.websocket_manager import ConnectionManager
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["valid", "cached", "missing", "corrupt"])
async def test_thumbnail_handler_uses_closed_owned_sessions_and_native_frames(
    tmp_path, monkeypatch, case
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    managers = [ConnectionManager(), ConnectionManager()]
    handlers = []
    paths = []
    queries = []
    accesses = []
    loop_thread = get_ident()
    native_stat = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path) in paths:
            accesses.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        for index, database in enumerate(databases):
            video = tmp_path / f"owner-{index}.mp4"
            thumbnail = video.with_name(video.stem + "-thumb.jpg")
            if case in {"valid", "cached"}:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=640x360:rate=5",
                        "-t",
                        "6",
                        "-threads",
                        "1",
                        "-c:v",
                        "mpeg4",
                        "-q:v",
                        "2",
                        str(video),
                    ],
                    check=True,
                    capture_output=True,
                )
            elif case == "corrupt":
                video.write_bytes(b"invalid media fixture")
            if case == "cached":
                subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(video),
                        "-vframes",
                        "1",
                        str(thumbnail),
                    ],
                    check=True,
                    capture_output=True,
                )
            paths.extend((str(video), str(thumbnail)))
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username=f"owner-{index}", twitch_id="same"))
                session.flush()
                session.add(Stream(id=1, streamer_id=1, recording_path=str(video)))
                session.flush()
                session.add(
                    Recording(
                        id=1,
                        stream_id=1,
                        status="completed",
                        start_time=datetime.now(timezone.utc),
                    )
                )
                if case == "cached":
                    session.add(
                        StreamMetadata(stream_id=1, thumbnail_path=str(thumbnail))
                    )
                session.commit()
            handlers.append(
                PostProcessingTaskHandlers(
                    session_factory=database.sync_session_factory,
                    connection_manager=managers[index],
                )
            )
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )

        for index, (database, handler) in enumerate(
            zip(databases, handlers, strict=True)
        ):
            video = tmp_path / f"owner-{index}.mp4"
            thumbnail = video.with_name(video.stem + "-thumb.jpg")
            with monkeypatch.context() as watched:
                watched.setattr(os, "stat", stat)
                payload = {"stream_id": 1, "recording_id": 1, "mp4_path": str(video)}
                if case in {"valid", "cached"}:
                    await handler.handle_thumbnail_generation(payload)
                else:
                    with pytest.raises(Exception, match="Thumbnail generation failed"):
                        await handler.handle_thumbnail_generation(payload)
            assert queries and loop_thread not in queries
            assert accesses and loop_thread not in accesses
            before_probe = len(queries)
            with database.sync_session_factory() as session:
                state = session.scalar(select(RecordingProcessingState))
                assert state.thumbnail_status == (
                    "completed" if case in {"valid", "cached"} else "failed"
                )
                metadata = session.scalar(select(StreamMetadata))
                if case in {"valid", "cached"}:
                    assert metadata.thumbnail_path == str(thumbnail)
                    with Image.open(thumbnail) as image:
                        assert image.format == "JPEG"
                        assert image.size == (640, 360)
                        image.verify()
                else:
                    assert metadata is None
                    assert not thumbnail.exists()
            if index == 0 and case != "cached":
                with databases[1].sync_session_factory() as session:
                    assert session.scalar(select(StreamMetadata)) is None
            del queries[before_probe:]
            assert database.sync_engine.pool.checkedout() == 0
    finally:
        for handler in handlers:
            await handler.cleanup()
        for manager in managers:
            await manager.close_all()
        for database in databases:
            await database.adispose()
