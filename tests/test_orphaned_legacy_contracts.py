"""Retained legacy SDK/storage contracts, not app off-loop/session guarantees."""

import importlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import (
    _close_application_logging,
    _close_application_proxy,
    _close_application_twitch,
)
from app.models import BackgroundTask, Recording, Stream
from app.services.recording.orphaned_recovery_service import (
    OrphanedRecoveryService,
    SegmentCleanupResult,
)
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
async def test_legacy_record_discovery_and_public_aliases_preserve_native_queue_payload(
    image_applications, monkeypatch
):
    apps, databases, _, _ = image_applications
    app, database = apps[0], databases[0]
    service = await run_in_thread_pool(
        dependencies.get_application_recovery_service,
        HTTPConnection({"type": "http", "app": app}),
    )
    adapter = OrphanedRecoveryService(service)
    now = datetime.now(timezone.utc)
    path = Path(app.state.settings.RECORDING_DIRECTORY) / "legacy.ts"
    path.write_bytes(b"synthetic SDK media" * 128)

    def seed():
        with database.sync_session_factory() as db:
            for offset, (status, created) in enumerate(
                (
                    ("failed", now - timedelta(days=7)),
                    ("recording", now),
                    ("completed", now - timedelta(days=7)),
                )
            ):
                db.add(Stream(id=70 + offset, streamer_id=1, ended_at=now))
                db.flush()
                db.add(
                    Recording(
                        id=7 + offset,
                        stream_id=70 + offset,
                        path=str(path),
                        status=status,
                        start_time=now,
                        created_at=created,
                    )
                )
            db.commit()

    await run_in_thread_pool(seed)
    queue_init = importlib.import_module("app.services.init.background_queue_init")
    native_enqueue = queue_init.enqueue_recording_post_processing
    observed = []

    async def enqueue(**payload):
        observed.append(dict(payload))
        return await native_enqueue(
            **payload,
            settings=app.state.settings,
            session_factory=database.sync_session_factory,
            queue_service=app.state.background_queue_service,
        )

    monkeypatch.setattr(queue_init, "enqueue_recording_post_processing", enqueue)
    try:
        with database.sync_session_factory() as db:
            found = await adapter._find_orphaned_recordings(db, max_age_hours=72)
            assert [row.id for row in found] == [7]
            row = found[0]
            assert (await adapter.validate_orphaned_recording(row))["valid"] is True
            assert await adapter.trigger_orphaned_recovery(row, db) is True
        assert len(observed) == 1
        assert observed[0]["recording_id"] == 7 and observed[0]["stream_id"] == 70
        assert observed[0]["ts_file_path"] == str(path)
        with database.sync_session_factory() as db:
            assert db.query(BackgroundTask).count() > 0
            assert db.get(Recording, 7).status == "failed"
        assert path.read_bytes() == b"synthetic SDK media" * 128
    finally:
        await app.state.recording_manager.shutdown()
        await app.state.background_queue_service.stop()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await _close_application_logging(app)
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dry_run,denied", [(True, False), (False, False), (False, True)]
)
async def test_legacy_segment_cleanup_retains_age_and_final_mp4_guards(
    tmp_path, monkeypatch, dry_run, denied
):
    adapter = OrphanedRecoveryService()
    root = tmp_path / "legacy"
    root.mkdir()
    adapter._service.recordings_base_path = root
    old = (datetime.now() - timedelta(days=7)).timestamp()
    for name in ("eligible", "recent", "no-final"):
        directory = root / f"{name}_segments"
        directory.mkdir()
        (directory / "piece.ts").write_bytes(name.encode())
        if name != "no-final":
            (root / f"{name}.mp4").write_bytes(b"existing final")
        if name != "recent":
            os.utime(directory, (old, old))
    if denied:
        import shutil

        native_remove = shutil.rmtree

        def remove(path, *args, **kwargs):
            if Path(path) == root / "eligible_segments":
                raise PermissionError("synthetic-legacy-segment-removal-denied")
            return native_remove(path, *args, **kwargs)

        monkeypatch.setattr(shutil, "rmtree", remove)
    result: SegmentCleanupResult = {
        "segments_cleaned": 0,
        "segments_cleaned_list": [],
        "errors": [],
    }
    await adapter._cleanup_orphaned_segments(None, 72, dry_run, result)
    assert (root / "recent_segments/piece.ts").read_bytes() == b"recent"
    assert (root / "no-final_segments/piece.ts").read_bytes() == b"no-final"
    assert (root / "eligible.mp4").read_bytes() == b"existing final"
    if denied:
        assert (
            result["segments_cleaned"] == 0
            and result.get("segments_cleanup_failed") == 1
        )
        assert "synthetic-legacy-segment-removal-denied" in result["errors"][0]
    else:
        assert result["segments_cleaned"] == 1
        assert result["segments_cleaned_list"] == [str(root / "eligible_segments")]
    assert (root / "eligible_segments").exists() is (dry_run or denied)


@pytest.mark.asyncio
async def test_legacy_singleton_shares_the_existing_busy_scan_guard(
    tmp_path, monkeypatch
):
    module = importlib.import_module("app.services.recording.orphaned_recovery_service")
    monkeypatch.setattr(module, "_recovery_service_instance", None)
    first = await module.get_orphaned_recovery_service()
    first._service.recordings_base_path = tmp_path / "never-created"
    first._service.is_running = True
    second = await module.get_orphaned_recovery_service()
    assert second is first
    assert (await second.get_orphaned_statistics())["total_orphaned"] == 0
    assert not first._service.recordings_base_path.exists()
