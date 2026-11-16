"""Native metadata embedding keeps model/FS work out of the process event loop."""

import builtins
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import importlib
import io
import json
import os
import subprocess
from threading import get_ident

import pytest
from sqlalchemy import event

from app.bootstrap.application import create_app
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer, StreamMetadata

from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "failure", "cancel", "publish-denied"])
async def test_native_embedding_uses_closed_owned_values_and_keeps_media_decodable(
    tmp_path, monkeypatch, outcome
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'embedding.db'}")
    root = tmp_path / "recordings"
    directory = root / "alice"
    directory.mkdir(parents=True)
    video = directory / "capture.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=256x256:rate=5",
            "-t",
            "2",
            "-c:v",
            "mpeg4",
            "-y",
            str(video),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    assert video.stat().st_size > 10000
    if outcome == "failure":
        video.write_bytes(b"invalid media" * 1000)
    original_bytes = video.read_bytes()
    peer_temp = directory / "capture.mp4.metadata.tmp"
    peer_temp.write_bytes(b"existing foreign metadata stage")
    chapter_file = directory / "capture-ffmpeg-chapters.txt"
    chapter_file.write_text(
        ";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Native chapter\n",
        encoding="utf-8",
    )
    application = create_app(
        Settings(
            ENVIRONMENT="test",
            RECORDING_DIRECTORY=str(root),
            LOGS_BASE_DIR=str(root / "logs"),
            _env_file=None,
        ),
        database=database,
    )
    handlers = application.state.background_queue_manager.task_handlers
    queries, probes = [], []
    children = []
    entered = asyncio.Event()
    loop_thread = get_ident()
    native_stat, native_open, native_io_open = os.stat, builtins.open, io.open
    native_replace = os.replace

    def observe(path):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            probes.append(get_ident())

    def stat(path, *args, **kwargs):
        observe(path)
        return native_stat(path, *args, **kwargs)

    def opened(path, *args, **kwargs):
        observe(path)
        return native_open(path, *args, **kwargs)

    def io_opened(path, *args, **kwargs):
        observe(path)
        return native_io_open(path, *args, **kwargs)

    def replace(source, destination):
        if outcome == "publish-denied" and str(destination) == str(video):
            raise PermissionError("synthetic metadata publication refusal")
        return native_replace(source, destination)

    def forbidden_logger():
        raise AssertionError("embedding must use its app's logger")

    logging_module = importlib.import_module("app.services.system.logging_service")
    monkeypatch.setattr(logging_module, "get_logging_service", forbidden_logger)
    metadata_module = importlib.import_module("app.services.media.metadata_service")
    native_process = metadata_module.media_process

    @asynccontextmanager
    async def observed_process(*command, **kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        assert all(isinstance(argument, str) for argument in command)
        if outcome == "cancel":
            command = (command[0], "-re", *command[1:])
        async with native_process(*command, **kwargs) as (process, output):
            children.append(process)
            entered.set()
            yield process, output

    monkeypatch.setattr(metadata_module, "media_process", observed_process)
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="alice", twitch_id="alice"))
            session.flush()
            started = datetime(2026, 11, 1, tzinfo=timezone.utc)
            session.add(
                Stream(
                    id=1,
                    streamer_id=1,
                    title="Native title",
                    category_name="Native game",
                    started_at=started,
                    ended_at=started + timedelta(seconds=2),
                    recording_path=str(video),
                )
            )
            session.flush()
            session.add(StreamMetadata(stream_id=1))
            session.commit()
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *_: queries.append(get_ident()),
        )
        with monkeypatch.context() as observed:
            observed.setattr(os, "stat", stat)
            observed.setattr(builtins, "open", opened)
            observed.setattr(io, "open", io_opened)
            observed.setattr(os, "replace", replace)
            operation = handlers.metadata_service.embed_all_metadata(
                str(video), str(chapter_file), 1
            )
            if outcome == "cancel":
                task = asyncio.create_task(
                    operation, name="metadata-cancellation-control"
                )
                try:
                    await asyncio.wait_for(entered.wait(), 3)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await asyncio.wait_for(task, 5)
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            else:
                assert await operation is (outcome == "success")
        assert queries and loop_thread not in queries
        assert probes and loop_thread not in probes
        assert peer_temp.read_bytes() == b"existing foreign metadata stage"
        assert list(directory.glob("*.metadata.tmp")) == [peer_temp]
        assert children and all(process.returncode is not None for process in children)
        for process in children:
            with pytest.raises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)
        assert database.sync_engine.pool.checkedout() == 0
        if outcome != "success":
            assert video.read_bytes() == original_bytes
            if outcome != "publish-denied":
                return
            assert await handlers.metadata_service.embed_all_metadata(
                str(video), str(chapter_file), 1
            )
            assert peer_temp.read_bytes() == b"existing foreign metadata stage"
            assert list(directory.glob("*.metadata.tmp")) == [peer_temp]
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-show_chapters",
                "-of",
                "json",
                str(video),
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
        decoded = json.loads(result.stdout)
        assert decoded["format"]["tags"]["title"] == "Native title"
        assert decoded["format"]["tags"]["artist"] == "alice"
        assert decoded["streams"][0]["codec_name"] == "mpeg4"
        assert decoded["chapters"][0]["tags"]["title"] == "Native chapter"
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await handlers.cleanup()
        await application.state.websocket_manager.close_all()
        if application.state.logging_service is not None:
            await run_in_thread_pool(application.state.logging_service.close)
        await database.adispose()
