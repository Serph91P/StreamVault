"""Cleanup preserves source guards and commits segment metadata in its own worker."""

import os
from datetime import datetime, timezone
from threading import get_ident

import pytest
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
@pytest.mark.parametrize(
    "case",
    [
        "post_processing",
        "deletion",
        "missing_mp4",
        "small_mp4",
        "denied_segments",
        "intelligent-timeout",
    ],
)
async def test_cleanup_closes_own_persistence_and_keeps_protected_sources(
    tmp_path, monkeypatch, case
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'cleanup.db'}")
    manager = ConnectionManager()
    handler = PostProcessingTaskHandlers(
        session_factory=database.sync_session_factory, connection_manager=manager
    )
    source = tmp_path / "source.ts"
    source.write_bytes(b"source must remain until the existing output guard passes")
    segments = tmp_path / "video_segments"
    segments.mkdir()
    (segments / "000.ts").write_bytes(b"segment")
    output = tmp_path / "output.mp4"
    # This is deliberately a size-guard fixture, not a claim of decoded media.
    if case not in {"deletion", "missing_mp4"}:
        with output.open("wb") as file:
            file.truncate(
                1024 * 1024 + 1
                if case in {"post_processing", "denied_segments", "intelligent-timeout"}
                else 100
            )
    loop_thread = get_ident()
    queries = []
    probes = []
    native_stat = os.stat
    import shutil

    native_rmtree = shutil.rmtree
    removal_faults = []

    def rmtree(path, *args, **kwargs):
        if case == "denied_segments" and str(path) == str(segments):
            removal_faults.append(get_ident())
            raise PermissionError("synthetic-owned-segment-removal-denied")
        return native_rmtree(path, *args, **kwargs)

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="cleanup", twitch_id="cleanup"))
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
            "mp4_path": str(output),
            "files_to_remove": [str(source), str(segments)],
        }
        if case == "deletion":
            payload["cleanup_paths"] = payload.pop("files_to_remove")
            payload.pop("mp4_path")
        if case == "intelligent-timeout":
            payload["intelligent_cleanup"] = True
            payload["max_wait_time"] = 0
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            watched.setattr(shutil, "rmtree", rmtree)
            if case in {
                "post_processing",
                "deletion",
                "denied_segments",
                "intelligent-timeout",
            }:
                await handler.handle_cleanup(payload)
            else:
                with pytest.raises(
                    Exception,
                    match="MP4 file not found"
                    if case == "missing_mp4"
                    else "MP4 file too small",
                ):
                    await handler.handle_cleanup(payload)
        assert probes and loop_thread not in probes
        assert loop_thread not in queries
        if case == "post_processing":
            assert queries
        with database.sync_session_factory() as session:
            metadata = session.scalar(select(StreamMetadata))
            state = session.scalar(select(RecordingProcessingState))
            if case in {"post_processing", "intelligent-timeout"}:
                assert metadata.segments_removed is True
                assert metadata.segments_dir_path == str(segments)
                assert state.cleanup_status == "completed"
                assert output.exists()
            elif case == "denied_segments":
                assert metadata is None or metadata.segments_removed is not True
                assert state.cleanup_status == "completed"
                assert output.exists()
            else:
                assert metadata is None
                assert state is None
        assert source.exists() is (
            case in {"missing_mp4", "small_mp4", "intelligent-timeout"}
        )
        assert segments.exists() is (
            case in {"missing_mp4", "small_mp4", "denied_segments"}
        )
        if case == "denied_segments":
            assert removal_faults and loop_thread not in removal_faults
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await handler.cleanup()
        await manager.close_all()
        await database.adispose()
