"""Cleanup preserves source guards and commits segment metadata in its own worker."""

import os
import sqlite3
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
        "intelligent-success",
        "scalar-deletion",
        "empty-deletion",
        "missing-path-deletion",
        "metadata-denied",
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
    output = tmp_path / (
        "source.mp4" if case == "intelligent-success" else "output.mp4"
    )
    # This is deliberately a size-guard fixture, not a claim of decoded media.
    if case not in {"deletion", "missing_mp4"}:
        with output.open("wb") as file:
            file.truncate(
                1024 * 1024 + 1
                if case
                in {
                    "post_processing",
                    "denied_segments",
                    "intelligent-timeout",
                    "intelligent-success",
                    "metadata-denied",
                }
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
        metadata_faults = []

        def observe_sql(_connection, _cursor, statement, *_args):
            queries.append(get_ident())
            if (
                case == "metadata-denied"
                and "STREAM_METADATA" in statement.upper()
                and not metadata_faults
            ):
                metadata_faults.append(get_ident())
                raise sqlite3.OperationalError(
                    "synthetic-owned-cleanup-metadata-denial"
                )

        event.listen(database.sync_engine, "before_cursor_execute", observe_sql)
        payload = {
            "stream_id": 1,
            "recording_id": 1,
            "mp4_path": str(output),
            "files_to_remove": [str(source), str(segments)],
        }
        if case == "deletion" or case.endswith("-deletion"):
            paths = payload.pop("files_to_remove")
            payload["cleanup_paths"] = (
                str(source)
                if case == "scalar-deletion"
                else None
                if case == "empty-deletion"
                else [str(tmp_path / "missing.ts")]
                if case == "missing-path-deletion"
                else paths
            )
            payload.pop("mp4_path")
        if case in {"intelligent-timeout", "intelligent-success"}:
            payload["intelligent_cleanup"] = True
            if case == "intelligent-timeout":
                payload["max_wait_time"] = 0
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            watched.setattr(shutil, "rmtree", rmtree)
            if case in {
                "post_processing",
                "deletion",
                "denied_segments",
                "intelligent-timeout",
                "intelligent-success",
                "scalar-deletion",
                "empty-deletion",
                "missing-path-deletion",
                "metadata-denied",
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
        if case != "empty-deletion":
            assert probes and loop_thread not in probes
        else:
            assert probes == []
        assert loop_thread not in queries
        if case == "post_processing":
            assert queries
        with database.sync_session_factory() as session:
            metadata = session.scalar(select(StreamMetadata))
            state = session.scalar(select(RecordingProcessingState))
            if case in {
                "post_processing",
                "intelligent-timeout",
                "intelligent-success",
            }:
                assert metadata.segments_removed is True
                assert metadata.segments_dir_path == str(segments)
                assert state.cleanup_status == "completed"
                assert output.exists()
            elif case in {"denied_segments", "metadata-denied"}:
                assert metadata is None or metadata.segments_removed is not True
                assert state.cleanup_status == "completed"
                assert output.exists()

            else:
                assert metadata is None
                assert state is None
        assert source.exists() is (
            case
            in {
                "missing_mp4",
                "small_mp4",
                "intelligent-timeout",
                "empty-deletion",
                "missing-path-deletion",
            }
        )
        assert segments.exists() is (
            case
            in {
                "missing_mp4",
                "small_mp4",
                "denied_segments",
                "scalar-deletion",
                "empty-deletion",
                "missing-path-deletion",
            }
        )
        if case == "denied_segments":
            assert removal_faults and loop_thread not in removal_faults
        if case == "metadata-denied":
            assert metadata_faults and loop_thread not in metadata_faults

        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await handler.cleanup()
        await manager.close_all()
        await database.adispose()
