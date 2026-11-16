"""Execute validation against native persistence/media, including corrupt outputs.

Value: protects=an empty or smaller TS does not reject a valid larger MP4;
fails_when=ratio/zero-size handling is inverted to false-reject a healthy output;
why_new=existing rows cover missing/small MP4 and an undersized ratio, not these skip branches;
seam=none; no_claim=provider capture or end-to-end job completion.
"""

import os
import subprocess
from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event, select

from app.database import Base, DatabaseLifecycle
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.services.communication.websocket_manager import ConnectionManager
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    ["valid", "missing", "small", "size_ratio", "larger_mp4", "empty_ts"],
)
async def test_validation_handler_closes_persistence_and_file_io_off_loop(
    tmp_path, monkeypatch, case
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'validation.db'}")
    manager = ConnectionManager()
    handler = PostProcessingTaskHandlers(
        session_factory=lambda: database.sync_session_factory(),
        connection_manager=manager,
    )
    path = tmp_path / "input.mp4"
    ts_path = tmp_path / "input.ts"
    valid_cases = {"valid", "larger_mp4", "empty_ts"}
    if case in valid_cases | {"size_ratio"}:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=1280x720:rate=30",
                "-t",
                "2",
                "-threads",
                "1",
                "-c:v",
                "mpeg4",
                "-q:v",
                "1",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        assert path.stat().st_size >= 1024 * 1024
        if case == "size_ratio":
            with ts_path.open("wb") as output:
                output.truncate(path.stat().st_size * 2)
        elif case == "larger_mp4":
            with ts_path.open("wb") as output:
                output.truncate(path.stat().st_size // 2)
        elif case == "empty_ts":
            ts_path.touch()
    elif case == "small":
        path.write_bytes(b"small")

    queries = []
    file_accesses = []
    loop_thread = get_ident()
    native_stat = os.stat

    def stat(candidate, *args, **kwargs):
        if isinstance(candidate, (str, os.PathLike)) and str(candidate) in {
            str(path),
            str(ts_path),
        }:
            file_accesses.append(get_ident())
        return native_stat(candidate, *args, **kwargs)

    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="validation", twitch_id="validation"))
            session.flush()
            session.add(Stream(id=1, streamer_id=1))
            session.flush()
            session.add(
                Recording(
                    id=1,
                    stream_id=1,
                    status="completed",
                    start_time=datetime.now(timezone.utc),
                )
            )
            session.commit()
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *_: queries.append(get_ident()),
        )
        payload = {
            "stream_id": 1,
            "recording_id": 1,
            "mp4_path": str(path),
            "ts_file_path": str(ts_path),
        }
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            if case in valid_cases:
                await handler.handle_mp4_validation(payload)
            else:
                expected = {
                    "missing": "MP4 file not found",
                    "small": "MP4 file too small",
                    "size_ratio": "MP4 file too small compared to TS",
                }[case]
                with pytest.raises(Exception, match=expected):
                    await handler.handle_mp4_validation(payload)
        operation_queries = queries.copy()
        with database.sync_session_factory() as session:
            state = session.scalar(select(RecordingProcessingState))
            assert state.mp4_validation_status == (
                "completed" if case in valid_cases else "failed"
            )
            if case not in valid_cases:
                assert expected in state.last_error
        assert operation_queries and loop_thread not in operation_queries
        assert file_accesses and loop_thread not in file_accesses
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await handler.cleanup()
        await manager.close_all()
        await database.adispose()
