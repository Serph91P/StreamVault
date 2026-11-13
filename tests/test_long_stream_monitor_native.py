"""Native long-stream monitor exits on owner removal/fencing/SQL fault, not age.

Value: protects=monitor refusal never kills cached child or borrows a peer catalog;
fails_when=fenced/failed heartbeat admits rotation, leaks task or changes peer state;
why_new=existing rotation tests replace monitor; these run its actual configured poll;
seam=none; no_claim=activated provider capture, authenticated handoff or durable media.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import Recording, Stream, TwitchUpstreamLease
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.retry_decorator import NonRetryableError
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["registry-removed", "fenced", "catalog-denied"])
async def test_native_long_stream_monitor_preserves_child_on_refusal(
    image_applications, monkeypatch, case
):
    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]
    app.state.settings.TWITCH_OAUTH_TOKEN = ""

    def seed():
        with database.sync_session_factory() as db:
            db.add(Stream(id=70, streamer_id=1))
            db.flush()
            db.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="recording",
                    start_time=datetime.now(timezone.utc),
                )
            )
            db.commit()

    await run_in_thread_pool(seed)
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    pm = lifecycle.process_manager
    stream = await lifecycle.database_service.get_stream_by_id(70)
    info = await pm._initialize_segmented_recording(
        stream,
        str(Path(app.state.settings.RECORDING_DIRECTORY) / "monitor.ts"),
        "best",
        7,
    )
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time;print('ready',flush=True);time.sleep(60)",
        stdout=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    reservation = None
    queries, listeners, rejected = [], [], []
    try:
        assert child.stdout is not None
        assert await asyncio.wait_for(child.stdout.readline(), 3) == b"ready\n"
        pm.active_processes["stream_70"] = child
        if case != "registry-removed":
            reservation = await pm.upstream_coordinator.reserve(
                channel_key="owner-0",
                auth_key=None,
                purpose="RECORDING",
                recording_id=7,
                prefer_authenticated=False,
            )
            info["upstream_channel_key"] = reservation.channel_key
            info["upstream_generation"] = reservation.generation
            if case == "fenced":
                await pm.upstream_coordinator.release(
                    channel_key=reservation.channel_key,
                    generation=reservation.generation,
                    reason="synthetic-monitor-released-before-poll",
                )
        else:
            native_decision = pm._should_rotate_segment

            async def removed_after_decision(metadata):
                result = await native_decision(metadata)
                pm.active_processes.pop("stream_70")
                return result

            monkeypatch.setattr(pm, "_should_rotate_segment", removed_after_decision)
        for index, owner in enumerate(databases):

            def observe(*_args, index=index):
                queries.append((index, get_ident()))
                if index == 0 and case == "catalog-denied":
                    rejected.append(True)
                    raise NonRetryableError("synthetic-owned-monitor-catalog-denial")

            event.listen(owner.sync_engine, "before_cursor_execute", observe)
            listeners.append(observe)
        # Real default/configured poll; no patched sleep, lease clock or timeout.
        await asyncio.wait_for(pm._monitor_long_stream(stream, info, "best"), 15)
        assert child.returncode is None
        assert info["segment_count"] == 1 and info["total_segments"] == []
        assert info["current_segment_path"].endswith("monitor_part001.ts")
        if case == "registry-removed":
            assert queries == [] and "stream_70" not in pm.active_processes
        else:
            assert pm.active_processes["stream_70"] is child
            assert queries and {owner for owner, _thread in queries} == {0}
            assert get_ident() not in {thread for _owner, thread in queries}
        if case == "catalog-denied":
            assert rejected
        assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
    finally:
        for owner, listener in zip(databases, listeners):
            event.remove(owner.sync_engine, "before_cursor_execute", listener)
        if child.returncode is None:
            child.terminate()
        await child.wait()
        pm.active_processes.pop("stream_70", None)
        if reservation is not None:
            await pm.upstream_coordinator.release(
                channel_key=reservation.channel_key,
                generation=reservation.generation,
                reason="synthetic-monitor-fixture-cleanup",
            )
        await close_owned(apps)
    with databases[1].sync_session_factory() as db:
        assert db.query(TwitchUpstreamLease).count() == 0
    assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
