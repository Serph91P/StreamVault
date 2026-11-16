"""Real TS→MP4 remux must close its sessions before owner-only delivery."""

import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event, select
from starlette.websockets import WebSocket

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
@pytest.mark.parametrize(
    "case", ["valid", "missing", "existing_output", "bad_chapters"]
)
async def test_real_remux_closes_io_and_delivers_only_to_its_owner(
    tmp_path, monkeypatch, case
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    handlers = []
    queues = [asyncio.Queue(), asyncio.Queue()]
    queries = []
    accesses = []
    deliveries = []
    loop_thread = get_ident()
    files = []
    original_stat = os.stat

    class ObservedManager(ConnectionManager):
        async def send_notification(self, message):
            if message["type"] == "recording_available":
                deliveries.append(message)
                assert all(
                    database.sync_engine.pool.checkedout() == 0
                    for database in databases
                )
            await super().send_notification(message)

    managers = [ObservedManager(), ObservedManager()]

    def watched_stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path) in files:
            accesses.append(get_ident())
        return original_stat(path, *args, **kwargs)

    async def receive():
        return {"type": "websocket.connect"}

    try:
        for index, database in enumerate(databases):
            directory = tmp_path / str(index)
            directory.mkdir()
            ts = directory / "input.ts"
            mp4 = directory / "output.mp4"
            chapter = directory / "chapters.txt"
            chapter.write_text(
                ";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=owner-"
                + str(index)
                + "\n"
            )
            if case == "bad_chapters":
                chapter.write_text(
                    ";FFMETADATA1\n[CHAPTER]\nSTART=invalid\nEND=1000\ntitle=invalid\n"
                )
            if case != "missing":
                subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=640x360:rate=25",
                        "-f",
                        "lavfi",
                        "-i",
                        "sine=frequency=440",
                        "-t",
                        "1",
                        "-threads",
                        "1",
                        "-c:v",
                        "mpeg2video",
                        "-b:v",
                        "3M",
                        "-c:a",
                        "aac",
                        str(ts),
                    ],
                    check=True,
                    capture_output=True,
                )
            if case == "existing_output":
                mp4.write_bytes(b"existing output must survive")
            files.extend((str(ts), str(mp4), str(chapter)))
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username=f"owner-{index}", twitch_id="same"))
                session.flush()
                session.add(
                    Stream(
                        id=1,
                        streamer_id=1,
                        title=f"title-{index}",
                        recording_path=str(ts),
                        started_at=datetime.now(timezone.utc),
                    )
                )
                session.flush()
                session.add(
                    Recording(
                        id=1,
                        stream_id=1,
                        status="completed",
                        start_time=datetime.now(timezone.utc),
                    )
                )
                session.add(
                    StreamMetadata(stream_id=1, chapters_ffmpeg_path=str(chapter))
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            handlers.append(
                PostProcessingTaskHandlers(
                    session_factory=database.sync_session_factory,
                    connection_manager=managers[index],
                )
            )

            async def send(message, index=index):
                await queues[index].put(message)

            socket = WebSocket(
                {"type": "websocket", "headers": [], "client": ("127.0.0.1", 12345)},
                receive,
                send,
            )
            assert await managers[index].connect(socket)

        for index, database in enumerate(databases):
            directory = tmp_path / str(index)
            ts = directory / "input.ts"
            mp4 = directory / "output.mp4"
            with monkeypatch.context() as watched:
                watched.setattr(os, "stat", watched_stat)
                payload = {
                    "stream_id": 1,
                    "recording_id": 1,
                    "ts_file_path": str(ts),
                    "mp4_output_path": str(mp4),
                    "streamer_name": f"owner-{index}",
                }
                if case in {"valid", "bad_chapters"}:
                    await handlers[index].handle_mp4_remux(payload)
                else:
                    with pytest.raises(
                        Exception,
                        match="TS file not found"
                        if case == "missing"
                        else "Output file already exists",
                    ):
                        await handlers[index].handle_mp4_remux(payload)
            assert loop_thread not in queries, (
                "remux persistence must remain in closed workers"
            )
            assert loop_thread not in accesses, (
                "remux filesystem access must not block the owner loop"
            )
            if case in {"valid", "bad_chapters"}:
                while True:
                    message = await asyncio.wait_for(queues[index].get(), 3)
                    if message["type"] == "websocket.send":
                        frame = json.loads(message["text"])
                        if frame["type"] == "recording_available":
                            break
                assert frame["data"] == {
                    "stream_id": 1,
                    "streamer_id": 1,
                    "streamer_name": f"owner-{index}",
                    "recording_path": str(mp4),
                    "title": f"title-{index}",
                }
                assert len(deliveries) == index + 1
                probe = json.loads(
                    subprocess.run(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-show_format",
                            "-show_chapters",
                            "-of",
                            "json",
                            str(mp4),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout
                )
                assert probe["format"]["tags"]["title"] == f"title-{index}"
                if case == "valid":
                    assert probe["chapters"][0]["tags"]["title"] == f"owner-{index}"
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "null", "-"],
                    check=True,
                    capture_output=True,
                )
            else:
                assert deliveries == []
                if case == "existing_output":
                    assert mp4.read_bytes() == b"existing output must survive"
            before_probe = len(queries)
            with database.sync_session_factory() as session:
                assert session.scalar(select(Stream.recording_path)) == str(
                    mp4 if case in {"valid", "bad_chapters"} else ts
                )
                state = session.scalar(select(RecordingProcessingState))
                assert state.mp4_remux_status == (
                    "completed" if case in {"valid", "bad_chapters"} else "failed"
                )
            del queries[before_probe:]
            assert database.sync_engine.pool.checkedout() == 0
        assert accesses and queries
        for index, queue in enumerate(queues):
            while not queue.empty():
                message = queue.get_nowait()
                if message["type"] == "websocket.send":
                    frame = json.loads(message["text"])
                    if frame["type"] == "recording_available":
                        assert frame["data"]["streamer_name"] == f"owner-{index}"
    finally:
        for handler in handlers:
            await handler.cleanup()
        for manager in managers:
            await manager.close_all()
        for database in databases:
            await database.adispose()
