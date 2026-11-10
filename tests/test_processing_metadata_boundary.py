"""Metadata queue input preparation owns its SQL and filesystem worker scope."""

from datetime import datetime, timezone
import os
from threading import get_ident

import pytest
from sqlalchemy import event

from app.database import Base, DatabaseLifecycle
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.services.communication.websocket_manager import ConnectionManager
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("authoritative", [True, False])
@pytest.mark.parametrize("outcome", ["success", "false", "error"])
async def test_metadata_handler_prepares_only_closed_scalar_paths_off_loop(
    tmp_path, monkeypatch, authoritative, outcome
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'metadata-input.db'}")
    manager = ConnectionManager()
    handler = PostProcessingTaskHandlers(
        session_factory=database.sync_session_factory, connection_manager=manager
    )
    root = tmp_path / "channel"
    root.mkdir()
    source = root / "recorded.ts"
    if authoritative:
        source.write_bytes(b"original capture bytes")
    output = tmp_path / "provided-output"
    queries, probes, calls, progress = [], [], [], []
    native_stat = os.stat
    loop_thread = get_ident()

    async def generate(*, stream_id, base_path, base_filename):
        assert database.sync_engine.pool.checkedout() == 0
        assert all(
            isinstance(value, (int, str))
            for value in (stream_id, base_path, base_filename)
        )
        calls.append((stream_id, base_path, base_filename))
        if outcome == "error":
            raise RuntimeError("synthetic metadata failure")
        return outcome == "success"

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(
        handler.metadata_service, "generate_metadata_for_stream", generate
    )
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="channel", twitch_id="channel"))
            session.flush()
            session.add(Stream(id=7, streamer_id=1, recording_path=str(source)))
            session.flush()
            session.add(
                Recording(
                    id=8,
                    stream_id=7,
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
            "stream_id": 7,
            "recording_id": 8,
            "output_dir": str(output),
            "base_filename": "provided.ts",
        }
        original = dict(payload)
        with monkeypatch.context() as observed:
            observed.setattr(os, "stat", stat)
            await handler.handle_metadata_generation(payload, progress.append)
        assert queries and loop_thread not in queries
        assert probes and loop_thread not in probes
        assert payload == original
        assert calls == [
            (
                7,
                str(root) if authoritative else str(output),
                "recorded" if authoritative else "provided",
            )
        ]
        assert progress == [10.0, 20.0, 90.0, 100.0]
        with database.sync_session_factory() as session:
            state = session.query(RecordingProcessingState).one()
            assert state.recording_id == 8
            assert state.metadata_status == (
                "completed" if outcome == "success" else "failed"
            )
        if authoritative:
            assert source.read_bytes() == b"original capture bytes"
            assert not output.exists()
        else:
            assert output.is_dir() and not source.exists()
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await handler.cleanup()
        await manager.close_all()
        await database.adispose()
