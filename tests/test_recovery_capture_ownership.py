"""Consistency repair must prove capture death, not infer it from age/files."""

import asyncio
import importlib
import sys
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Recording, Stream, Streamer, TwitchUpstreamLease
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_manager import RecordingManager
from app.services.recording.unified_recovery_service import (
    RecoveryStats,
    UnifiedRecoveryService,
)
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "active_local",
        "active_foreign",
        "expired_live",
        "identity_mismatch",
        "handoff_starting",
        "unknown_without_metadata",
        "dead_foreign",
        "startup_dead",
        "stopped_but_live",
    ],
)
async def test_consistency_repair_requires_positive_death_proof(
    tmp_path, monkeypatch, case
):
    import app.services.recording.unified_recovery_service as recovery

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
    factory = sessionmaker(engine)
    root = tmp_path / "recordings"
    directory = root / "synthetic952" / "Season 2026"
    directory.mkdir(parents=True)
    media = directory / "synthetic952.ts"
    media.write_bytes(b"original synthetic capture" * 100)
    start = datetime.now(timezone.utc) - timedelta(hours=8)
    with factory() as db:
        streamer = Streamer(username="synthetic952", twitch_id="952")
        db.add(streamer)
        db.flush()
        stream = Stream(streamer_id=streamer.id, started_at=start)
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id,
            status="stopped" if case == "stopped_but_live" else "recording",
            path=str(media),
            start_time=start,
        )
        db.add(recording)
        db.commit()
        stream_id, recording_id = stream.id, recording.id
    coordinator = TwitchUpstreamCoordinator(factory, monotonic_clock=time.monotonic)
    manager = object.__new__(ProcessManager)
    manager.active_processes = {}
    manager.long_stream_processes = {}
    manager.lock = asyncio.Lock()
    manager.upstream_coordinator = coordinator
    cache = {}
    child = None
    try:
        if case != "unknown_without_metadata":
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import sys,time;f=open(sys.argv[1],'ab');f.write(b' native writer');f.flush();print('ready',flush=True);time.sleep(60)",
                str(media),
                stdout=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            assert await child.stdout.readline() == b"ready\n"
            identity = await coordinator.inspect_process_identity(child.pid)
            if case in {"dead_foreign", "startup_dead"}:
                child.kill()
                await child.wait()
            if case == "active_local":
                manager.active_processes[f"stream_{stream_id}"] = child
                manager.long_stream_processes[f"stream_{stream_id}"] = {
                    "upstream_process_group_id": identity.process_group_id,
                    "upstream_process_start_fingerprint": identity.fingerprint,
                    "upstream_generation": 1,
                }
                cache[recording_id] = {"stream_id": stream_id, "file_path": str(media)}
            else:
                with factory() as db:
                    db.add(
                        TwitchUpstreamLease(
                            channel_key="952",
                            recording_id=recording_id,
                            purpose="RECORDING",
                            state="STARTING"
                            if case == "handoff_starting"
                            else "ACTIVE",
                            generation=2 if case == "handoff_starting" else 1,
                            process_pid=None
                            if case == "handoff_starting"
                            else child.pid,
                            process_group_id=identity.process_group_id,
                            process_started_at=identity.started_at,
                            process_start_fingerprint="not-the-child"
                            if case == "identity_mismatch"
                            else identity.fingerprint,
                            reserved_at=start,
                            heartbeat_at=start,
                            expires_at=start
                            if case == "expired_live"
                            else datetime.now(timezone.utc) + timedelta(seconds=60),
                            created_at=start,
                            updated_at=start,
                        )
                    )
                    db.commit()
                if case == "startup_dead":
                    cache[recording_id] = {
                        "stream_id": stream_id,
                        "file_path": str(media),
                    }
        facade = RecordingManager.__new__(RecordingManager)
        facade._service = SimpleNamespace(
            process_manager=manager, get_active_recordings=lambda: cache
        )
        monkeypatch.setattr(recovery, "SessionLocal", factory)
        monkeypatch.setattr(recovery, "get_recording_manager", lambda: facade)
        monkeypatch.setattr(
            importlib.import_module("app.dependencies"),
            "get_recording_manager",
            lambda: facade,
        )
        service = UnifiedRecoveryService()
        service.recordings_base_path = root
        before = media.read_bytes()
        with factory() as db:
            leases = list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
        stats = RecoveryStats()
        await service._fix_database_inconsistencies(stats, dry_run=False)
        dead = case in {"dead_foreign", "startup_dead"}
        with factory() as db:
            row = db.get(Recording, recording_id)
            assert row.status == (
                "completed"
                if dead
                else "stopped"
                if case == "stopped_but_live"
                else "recording"
            )
            assert (row.end_time is not None) is dead
            assert stats.updated_database_entries == int(dead)
            assert (
                list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
                == leases
            )
        assert (str(media) in await service._get_active_recording_paths()) is not dead
        from app.services.recording.orphaned_recovery_service import (
            OrphanedRecoveryService,
        )

        with factory() as db:
            validation = await OrphanedRecoveryService().validate_orphaned_recording(
                db.get(Recording, recording_id)
            )
        assert validation["valid"] is dead
        if not dead:
            touched = []

            async def enqueue(**payload):
                touched.append("enqueue")
                return True

            async def provider_boundary(recording_id):
                touched.append("provider")
                raise RuntimeError("synthetic stop before any provider or conversion")

            monkeypatch.setattr(recovery, "enqueue_recording_post_processing", enqueue)
            monkeypatch.setattr(
                service, "_check_if_streamer_still_live", provider_boundary
            )
            assert (
                await service._retry_post_processing(
                    {
                        "recording_id": recording_id,
                        "ts_path": media,
                        "streamer_name": "synthetic952",
                        "type": "existing_ts",
                    }
                )
                is False
            )
            assert (
                await service._process_orphaned_recording(
                    {
                        "recording_id": recording_id,
                        "expected_ts_path": media,
                        "segments_dir": directory / "synthetic952_segments",
                        "streamer_name": "synthetic952",
                    }
                )
                is False
            )
            assert touched == []
            monkeypatch.setattr(
                importlib.import_module("app.services.init.background_queue_init"),
                "enqueue_recording_post_processing",
                enqueue,
            )
            with factory() as db:
                assert (
                    await OrphanedRecoveryService().trigger_orphaned_recovery(
                        db.get(Recording, recording_id), db
                    )
                    is False
                )
            assert touched == []
        if case == "active_foreign":
            with factory() as db:
                db.execute(
                    update(Stream)
                    .where(Stream.id == stream_id)
                    .values(title="uncommitted caller state")
                )
                await OrphanedRecoveryService().validate_orphaned_recording(
                    db.get(Recording, recording_id)
                )
                assert (
                    db.scalar(select(Stream.title).where(Stream.id == stream_id))
                    == "uncommitted caller state"
                )
        assert media.read_bytes() == before
        assert media.stat().st_nlink == 1
        if child and not dead:
            assert child.returncode is None
    finally:
        if child:
            if child.returncode is None:
                child.kill()
            await child.wait()
        engine.dispose()
