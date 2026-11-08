"""Recovery's coordination guard must not span an unbounded storage scan."""

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Recording, Stream, Streamer
from app.services.recording import media_ownership
from app.services.recording.process_manager import ProcessManager
from app.services.recording.unified_recovery_service import (
    RecoveryStats,
    UnifiedRecoveryService,
)
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["recovery", "periodic"])
async def test_unknown_prefix_cannot_hide_later_dead_capture_or_hold_unbounded_guard(
    tmp_path, monkeypatch, operation
):
    from app.services.recording import unified_recovery_service as module

    engine = create_engine(f"sqlite:///{tmp_path / 'bounded.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    sessions = sessionmaker(engine)
    media = tmp_path / "synthetic.ts"
    media.write_bytes(b"unchanged capture source")
    with sessions() as db:
        channel = Streamer(username="bounded", twitch_id="bounded")
        db.add(channel)
        db.flush()
        final_stream = 0
        for n in range(201):
            stream = Stream(
                streamer_id=channel.id, started_at=datetime.now(timezone.utc)
            )
            db.add(stream)
            db.flush()
            db.add(
                Recording(
                    stream_id=stream.id,
                    start_time=stream.started_at,
                    status="recording",
                    path=str(media),
                )
            )
            final_stream = stream.id
        db.commit()
    child = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
    await child.wait()
    processes = object.__new__(ProcessManager)
    processes.lock = asyncio.Lock()
    processes.active_processes = {f"stream_{final_stream}": child}
    processes.long_stream_processes = {}
    coordinator = processes.upstream_coordinator = TwitchUpstreamCoordinator(
        sessions, monotonic_clock=time.monotonic
    )
    state = SimpleNamespace(
        get_active_recordings=lambda: {},
        get_active_recording=lambda _: None,
        remove_active_recording=lambda _: None,
    )
    manager = SimpleNamespace(
        process_manager=processes, orchestrator=SimpleNamespace(state_manager=state)
    )
    monkeypatch.setattr(module, "get_recording_manager", lambda: manager)
    monkeypatch.setattr(module, "SessionLocal", sessions)
    native = coordinator.run_capture_maintenance
    original_state = media_ownership.capture_state
    native_stat = Path.stat
    calls = [0]
    guarded = [False]
    widths = []
    storage_under_guard = []
    peer_admissions = []

    def inspect_state(*args):
        calls[0] += 1
        return original_state(*args)

    def inspect_stat(path, *args, **kwargs):
        if path == media and guarded[0]:
            storage_under_guard.append(str(path))
        return native_stat(path, *args, **kwargs)

    async def observe(operation):
        def guarded_operation(db):
            before = calls[0]
            guarded[0] = True
            try:
                return operation(db)
            finally:
                widths.append(calls[0] - before)
                guarded[0] = False

        result = await native(guarded_operation)
        # A separate guarded transaction can acquire admission between recovery batches.
        peer = asyncio.create_task(native(lambda db: peer_admissions.append(True) or 0))
        await asyncio.wait_for(peer, 2)
        return result

    monkeypatch.setattr(media_ownership, "capture_state", inspect_state)
    monkeypatch.setattr(Path, "stat", inspect_stat)
    monkeypatch.setattr(coordinator, "run_capture_maintenance", observe)
    try:
        if operation == "recovery":
            stats = RecoveryStats()
            await UnifiedRecoveryService()._fix_database_inconsistencies(stats, False)
            assert stats.updated_database_entries == 1
            final_status = "completed"
        else:
            from app.services.init.startup_init import _cleanup_zombie_recordings_now

            assert await _cleanup_zombie_recordings_now(recording_manager=manager) == 1
            final_status = "stopped"
        with sessions() as db:
            assert (
                db.query(Recording).filter(Recording.status == "recording").count()
                == 200
            )
            assert (
                db.query(Recording)
                .filter(Recording.status == final_status)
                .one()
                .stream_id
                == final_stream
            )
        assert widths and max(widths) <= 100
        assert len(widths) >= 3
        assert not storage_under_guard
        assert len(peer_admissions) == len(widths)
        assert media.read_bytes() == b"unchanged capture source"
    finally:
        engine.dispose()
