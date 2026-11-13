"""Discovery is read-only; explicit adoption is idempotent (#951)."""

import asyncio
import importlib
import os
from datetime import datetime, timedelta, timezone
from threading import get_ident
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Recording, Stream, Streamer
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_manager import RecordingManager
from app.services.recording.unified_recovery_service import UnifiedRecoveryService


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'discovery.db'}")
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
    factory = sessionmaker(engine)
    with factory() as db:
        streamer = Streamer(username="synthetic", twitch_id="synthetic951")
        db.add(streamer)
        db.flush()
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        db.add(
            Stream(
                streamer_id=streamer.id,
                title="offline",
                started_at=start,
                ended_at=start + timedelta(hours=1),
            )
        )
        db.commit()
    root = tmp_path / "recordings"
    directory = root / "synthetic" / "Season 2026"
    directory.mkdir(parents=True)
    manager = RecordingManager.__new__(RecordingManager)
    processes = object.__new__(ProcessManager)
    processes.active_processes = {}
    processes.long_stream_processes = {}
    processes.lock = asyncio.Lock()
    manager._service = SimpleNamespace(
        get_active_recordings=lambda: {}, process_manager=processes
    )
    module = importlib.import_module("app.services.recording.unified_recovery_service")
    monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(module, "get_recording_manager", lambda: manager)
    service = UnifiedRecoveryService()
    service.recordings_base_path = root
    yield service, factory, directory
    engine.dispose()


def tables(factory):
    with factory() as db:
        return {
            table.name: list(db.execute(select(table)).tuples())
            for table in Base.metadata.sorted_tables
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["segments", "ts"])
async def test_missing_row_lookup_does_not_adopt(discovery, kind):
    service, factory, directory = discovery
    path = directory / "synthetic_orphan.ts"
    if kind == "segments":
        segments = directory / "synthetic_orphan_segments"
        segments.mkdir()
        (segments / "segment_001.ts").write_bytes(b"original segment bytes")
    else:
        path.write_bytes(b"original TS bytes")
    before = tables(factory)
    result = await service._batch_find_recordings_by_paths([str(path)])
    assert tables(factory) == before
    assert result == {str(path): None}


@pytest.mark.asyncio
async def test_comprehensive_preview_uses_native_facade_without_writes(discovery):
    service, factory, directory = discovery
    segments = directory / "synthetic_orphan_segments"
    segments.mkdir()
    original = segments / "segment_001.ts"
    original.write_bytes(b"original segment bytes")
    before = tables(factory)
    for _ in range(2):
        stats = await service.comprehensive_recovery_scan(dry_run=True)
        assert stats.orphaned_segments == 1
        assert stats.recovered_recordings == stats.triggered_post_processing == 0
        assert tables(factory) == before
        assert original.read_bytes() == b"original segment bytes"


@pytest.mark.asyncio
async def test_only_real_processing_adopts_before_provider_decision(
    discovery, monkeypatch
):
    service, factory, directory = discovery
    segments = directory / "synthetic_orphan_segments"
    segments.mkdir()
    original = segments / "segment_001.ts"
    original.write_bytes(b"original segment bytes")
    seen = []

    async def stop_at_provider_decision(recording_id):
        seen.append(recording_id)
        raise RuntimeError("synthetic stop at provider boundary; no network or ffmpeg")

    monkeypatch.setattr(
        service, "_check_if_streamer_still_live", stop_at_provider_decision
    )
    result = await service._process_orphaned_recording(
        {
            "recording_id": None,
            "streamer_name": "synthetic",
            "segments_dir": segments,
            "expected_ts_path": directory / "synthetic_orphan.ts",
        }
    )
    assert (
        result is False
    )  # Deliberately stopped after admission, not a conversion pass.
    with factory() as db:
        rows = db.scalars(select(Recording)).all()
        assert len(rows) == 1
        assert seen == [rows[0].id]
    assert original.read_bytes() == b"original segment bytes"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["segments", "ts"])
async def test_explicit_adoption_reuses_one_row_across_service_instances(
    discovery, kind
):
    service, factory, directory = discovery
    path = directory / "synthetic_orphan.ts"
    if kind == "ts":
        path.write_bytes(b"original TS bytes")
    else:
        segments = directory / "synthetic_orphan_segments"
        segments.mkdir()
        (segments / "segment_001.ts").write_bytes(b"original segment bytes")

    async def adopt(instance):
        return await instance._adopt_recording(str(path))

    ids = await asyncio.gather(adopt(service), adopt(UnifiedRecoveryService()))
    assert ids[0] is not None and ids[0] == ids[1]
    with factory() as db:
        assert len(db.scalars(select(Recording)).all()) == 1
        assert len(db.scalars(select(Stream)).all()) == 1
    assert await service._batch_find_recordings_by_paths([str(path)]) == {
        str(path): ids[0]
    }


@pytest.mark.asyncio
async def test_concat_completion_requires_post_processing_admission(
    discovery, monkeypatch
):
    service, factory, directory = discovery
    segments = directory / "synthetic_small_segments"
    segments.mkdir()
    original = segments / "segment_001.ts"
    child = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=8000:cl=mono",
        "-t",
        "0.001",
        "-c:a",
        "aac",
        "-b:a",
        "8k",
        "-f",
        "mpegts",
        str(original),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, error = await child.communicate()
    assert child.returncode == 0, error.decode()
    source_bytes = original.read_bytes()
    probes = []
    loop_thread = get_ident()
    native_stat = os.stat
    native_scandir = os.scandir

    def scandir(path):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(
            str(directory)
        ):
            probes.append(get_ident())
        return native_scandir(path)

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(
            str(directory)
        ):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    async def offline(recording_id):
        return False  # Only the external provider decision is controlled here.

    monkeypatch.setattr(service, "_check_if_streamer_still_live", offline)
    output = directory / "synthetic_small.ts"
    with monkeypatch.context() as watched:
        watched.setattr(os, "stat", stat)
        watched.setattr(os, "scandir", scandir)
        result = await service._process_orphaned_recording(
            {
                "recording_id": None,
                "streamer_name": "synthetic",
                "segments_dir": segments,
                "expected_ts_path": output,
            }
        )
    assert result is False  # A real concatenation is not an accepted processing chain.
    assert probes and loop_thread not in probes
    assert 0 < output.stat().st_size < 1024
    assert original.read_bytes() == source_bytes
    assert factory.kw["bind"].pool.checkedout() == 0
