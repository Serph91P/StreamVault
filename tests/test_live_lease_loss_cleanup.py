"""Live lease-loss cleanup using actual children, pipes and persisted leases.

Python children stand in for upstream/ffmpeg; no provider/media conversion claim.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import TwitchUpstreamLease
from app.services.live_streaming_service import LiveStreamSession, LiveStreamingService
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator


@pytest_asyncio.fixture
async def live(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
    factory = sessionmaker(engine)
    coordinator = TwitchUpstreamCoordinator(factory, monotonic_clock=time.monotonic)
    children = []

    async def spawn(code, **kwargs):
        child = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code, start_new_session=True, **kwargs
        )
        children.append(child)
        return child

    upstream = await spawn(
        "import sys,time;sys.stdout.buffer.write(b'x'*4096);sys.stdout.flush();time.sleep(60)",
        stdout=asyncio.subprocess.PIPE,
    )
    sink = await spawn(
        "import sys;sys.stdin.buffer.read()", stdin=asyncio.subprocess.PIPE
    )
    origin = await coordinator.inspect_process_identity(upstream.pid)
    sink_origin = await coordinator.inspect_process_identity(sink.pid)
    directory = tmp_path / "owned-live"
    directory.mkdir()
    (directory / "fragment.ts").write_bytes(b"owned synthetic fragment")
    session = LiveStreamSession(
        "owned956",
        "synthetic",
        "best",
        upstream,
        sink,
        directory,
        channel_key="synthetic956",
        lease_generation=1,
        process_group_id=origin.process_group_id,
        process_started_at=origin.started_at,
        process_start_fingerprint=origin.fingerprint,
        ffmpeg_process_group_id=sink_origin.process_group_id,
        ffmpeg_process_start_fingerprint=sink_origin.fingerprint,
    )
    service = LiveStreamingService(coordinator=coordinator, output_root=tmp_path)
    service.sessions[session.session_id] = session
    for label, child in (("streamlink", upstream), ("ffmpeg", sink)):
        service._supervisor.track_process(f"{session.session_id}:{label}", child)
    pipe = service._supervisor.create_task(
        f"{session.session_id}:media-pipe",
        service._pipe_streamlink_to_ffmpeg(upstream, sink),
    )
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(
            TwitchUpstreamLease(
                channel_key=session.channel_key,
                live_session_id=session.session_id,
                purpose="LIVE",
                state="ACTIVE",
                generation=1,
                process_pid=upstream.pid,
                process_group_id=origin.process_group_id,
                process_started_at=origin.started_at,
                process_start_fingerprint=origin.fingerprint,
                reserved_at=now,
                activated_at=now,
                heartbeat_at=now,
                expires_at=now + timedelta(seconds=30),
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    try:
        yield service, session, coordinator, factory, spawn, pipe
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        await service._supervisor.shutdown()
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["revoked", "expired", "replacement"])
async def test_heartbeat_loss_reaps_owned_children_and_pipe(live, reason):
    service, session, coordinator, factory, spawn, pipe = live
    replacement = None
    if reason == "replacement":
        replacement = await spawn("import time;time.sleep(60)")
        identity = await coordinator.inspect_process_identity(replacement.pid)
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        if replacement:
            lease.generation = 2
            lease.live_session_id = "foreign956"
            lease.process_pid = identity.pid
            lease.process_group_id = identity.process_group_id
            lease.process_started_at = identity.started_at
            lease.process_start_fingerprint = identity.fingerprint
        else:
            lease.state = "RELEASED"
            lease.release_reason = reason
            lease.released_at = datetime.now(timezone.utc)
            lease.expires_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.commit()
        before = list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
    await asyncio.wait_for(service._monitor_session(session.session_id), 3)
    assert session.streamlink_process.returncode is not None
    assert session.ffmpeg_process.returncode is not None
    assert pipe.done()
    assert service._supervisor.process_names == ()
    assert session.session_id not in service.sessions
    assert not session.output_dir.exists()
    assert await service.stop_stream(session.session_id) is False
    if replacement:
        assert replacement.returncode is None
    with factory() as db:
        assert (
            list(db.execute(select(TwitchUpstreamLease.__table__)).tuples()) == before
        )


@pytest.mark.asyncio
async def test_inactive_session_is_idempotently_cleanable(live):
    service, session, _, _, _, pipe = live
    session.is_active = False
    assert await service.stop_stream(session.session_id) is True
    assert await service.stop_stream(session.session_id) is False
    assert session.streamlink_process.returncode is not None
    assert session.ffmpeg_process.returncode is not None
    assert pipe.done()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "protection", ["fingerprint_mismatch", "replacement_adopts_same_process"]
)
async def test_lease_loss_never_signals_foreign_identity_but_cleans_local_sink(
    live, protection
):
    service, session, _, factory, _, pipe = live
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        if protection == "replacement_adopts_same_process":
            lease.generation = 2
            lease.live_session_id = "replacement956"
        else:
            lease.state = "RELEASED"
            session.process_start_fingerprint = "not-the-child-fingerprint"
        db.commit()
        before = list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
    await asyncio.wait_for(service._monitor_session(session.session_id), 3)
    assert session.streamlink_process.returncode is None
    assert session.ffmpeg_process.returncode is not None
    assert pipe.done()
    assert not session.is_active
    with factory() as db:
        assert (
            list(db.execute(select(TwitchUpstreamLease.__table__)).tuples()) == before
        )


@pytest.mark.asyncio
async def test_inactive_old_child_cleanup_does_not_release_same_generation_replacement(
    live,
):
    service, session, coordinator, factory, spawn, pipe = live
    replacement = await spawn("import time;time.sleep(60)")
    identity = await coordinator.inspect_process_identity(replacement.pid)
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        lease.live_session_id = "new-owner-same-generation"
        lease.process_pid = identity.pid
        lease.process_group_id = identity.process_group_id
        lease.process_started_at = identity.started_at
        lease.process_start_fingerprint = identity.fingerprint
        db.commit()
        before = list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
    session.is_active = False
    assert await service.stop_stream(session.session_id) is True
    assert pipe.done()
    assert session.streamlink_process.returncode is not None
    assert session.ffmpeg_process.returncode is not None
    assert replacement.returncode is None
    with factory() as db:
        assert (
            list(db.execute(select(TwitchUpstreamLease.__table__)).tuples()) == before
        )


@pytest.mark.asyncio
async def test_native_started_service_shutdown_preserves_replacement_owner(
    live, monkeypatch, tmp_path
):
    _, _, coordinator, factory, _, _ = live
    service = LiveStreamingService(
        coordinator=coordinator, output_root=tmp_path / "native-start"
    )
    monkeypatch.setenv("FFMPEG_PATH", sys.executable)

    async def upstream_command(*args, **kwargs):
        return [
            sys.executable,
            "-c",
            "import sys,time;sys.stdout.buffer.write(b'x'*4096);sys.stdout.flush();time.sleep(60)",
        ]

    def sink_command(output_dir):
        return [
            sys.executable,
            "-c",
            "import pathlib,sys;pathlib.Path(sys.argv[1]).write_text('#EXTM3U\\n');sys.stdin.buffer.read()",
            str(output_dir / "playlist.m3u8"),
        ]

    monkeypatch.setattr(service, "_build_streamlink_command", upstream_command)
    monkeypatch.setattr(service, "_build_ffmpeg_command", sink_command)
    result = await service._start_stream_once("native956")
    session = service.sessions[result.session_id]
    try:
        with factory() as db:
            lease = db.scalar(
                select(TwitchUpstreamLease).where(
                    TwitchUpstreamLease.channel_key == "native956"
                )
            )
            lease.generation += 1
            lease.live_session_id = "replacement-owner"
            db.commit()
            before = list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
        await service.stop()
        assert session.streamlink_process.returncode is None
        assert session.ffmpeg_process.returncode is not None
        assert service._supervisor.task_names == ()
        with factory() as db:
            assert (
                list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
                == before
            )
    finally:
        for child in (session.streamlink_process, session.ffmpeg_process):
            if child.returncode is None:
                child.kill()
            await child.wait()
        await service._supervisor.shutdown()


@pytest.mark.asyncio
async def test_concurrent_inactive_stops_share_one_cleanup(live):
    service, session, _, _, _, pipe = live
    session.is_active = False
    results = await asyncio.gather(
        service.stop_stream(session.session_id), service.stop_stream(session.session_id)
    )
    assert sorted(results) == [False, True]
    assert session.streamlink_process.returncode is not None
    assert session.ffmpeg_process.returncode is not None
    assert pipe.done()


@pytest.mark.asyncio
async def test_monitor_cancellation_drains_started_lease_loss_cleanup(
    live, monkeypatch
):
    service, session, coordinator, factory, _, pipe = live
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        lease.state = "RELEASED"
        db.commit()
    entered, proceed = asyncio.Event(), asyncio.Event()
    original = coordinator.inspect_process_identity

    async def inspect(process_pid):
        if process_pid == session.streamlink_process.pid:
            entered.set()
            await proceed.wait()
        return await original(process_pid)

    monkeypatch.setattr(coordinator, "inspect_process_identity", inspect)
    monitor = asyncio.create_task(service._monitor_session(session.session_id))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        monitor.cancel()
        proceed.set()
        with pytest.raises(asyncio.CancelledError):
            await monitor
        assert session.streamlink_process.returncode is not None
        assert session.ffmpeg_process.returncode is not None
        assert pipe.done()
        assert session.session_id not in service.sessions
    finally:
        proceed.set()
        if not monitor.done():
            monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)
