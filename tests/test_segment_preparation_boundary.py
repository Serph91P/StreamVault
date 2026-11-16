"""Native normal/resume segment preparation preserves files and loop ownership.

Value: protects=next segment identity, untouched sources and drained cancellation;
fails_when=filesystem on loop, wrong part numbering or registry published after cancel;
why_new=owned start failure covers refusal, not real initializer success/resume/drain;
seam=none; no_claim=provider execution, decoded media, activated capture or lease authority.
"""

import asyncio
import os
from pathlib import Path
from threading import Event as ThreadEvent, get_ident

import pytest
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "layout,part",
    [
        ("normal", "capture_part001.ts"),
        ("numbered", "capture_part011.ts"),
        ("empty", "capture_part001.ts"),
        ("unparsed", "capture_part001.ts"),
        ("cancel", None),
    ],
)
async def test_native_segment_paths_keep_existing_sources_and_draining_boundary(
    image_applications, monkeypatch, layout, part
):
    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]
    root = Path(app.state.settings.RECORDING_DIRECTORY)
    segments = root / "capture_segments"
    peer = Path(apps[1].state.settings.RECORDING_DIRECTORY) / "capture_segments"
    peer.mkdir()
    protected = peer / "capture_part900.ts"
    protected.write_bytes(b"peer segment must survive")
    originals = {}
    if layout in {"numbered", "empty", "unparsed"}:
        segments.mkdir()
        names = (
            ["capture_part001.ts", "capture_part010.ts"]
            if layout == "numbered"
            else ["capture_partbogus.ts"]
            if layout == "unparsed"
            else []
        )
        for name in names:
            originals[name] = b"existing segment bytes, no decoding claim"
            (segments / name).write_bytes(originals[name])

    def seed():
        with database.sync_session_factory() as db:
            db.add(Stream(id=70, streamer_id=1))
            db.commit()

    await run_in_thread_pool(seed)
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    process_manager = manager.orchestrator.lifecycle_manager.process_manager
    stream = (
        await manager.orchestrator.lifecycle_manager.database_service.get_stream_by_id(
            70
        )
    )
    assert database.sync_engine.pool.checkedout() == 0
    native_stat, native_scan, native_mkdir = os.stat, os.scandir, Path.mkdir
    probes = []
    entered, release = ThreadEvent(), ThreadEvent()

    def observed(path):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(root)):
            probes.append(get_ident())
            return True
        return False

    def stat(path, *args, **kwargs):
        observed(path)
        return native_stat(path, *args, **kwargs)

    def scan(path):
        observed(path)
        return native_scan(path)

    def mkdir(path, *args, **kwargs):
        if observed(path) and layout == "cancel":
            entered.set()
            assert release.wait(5)
        return native_mkdir(path, *args, **kwargs)

    operation = None
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(os, "stat", stat)
            scoped.setattr(os, "scandir", scan)
            scoped.setattr(Path, "mkdir", mkdir)
            operation = asyncio.create_task(
                process_manager._initialize_segmented_recording(
                    stream,
                    str(root / "capture.ts"),
                    "best",
                    7,
                    str(segments)
                    if layout in {"numbered", "empty", "unparsed"}
                    else None,
                )
            )
            if layout == "cancel":
                assert await asyncio.to_thread(entered.wait, 3)
                operation.cancel()
                await asyncio.sleep(0)
                operation.cancel()
                await asyncio.sleep(0)
                assert not operation.done()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await operation
                assert "stream_70" not in process_manager.long_stream_processes
            else:
                result = await operation
                assert result["current_segment_path"] == str(segments / part)
                assert result["segment_count"] == (11 if layout == "numbered" else 1)
                assert result["recording_id"] == 7 and result["stream_id"] == 70
                assert result["total_segments"] == [] and result["monitor_task"] is None
                assert process_manager.long_stream_processes["stream_70"] is result
        assert probes and get_ident() not in probes
        assert {
            path.name: path.read_bytes() for path in segments.iterdir()
        } == originals
        assert protected.read_bytes() == b"peer segment must survive"
        assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
    finally:
        release.set()
        if operation is not None:
            if not operation.done():
                operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
        await close_owned(apps)
