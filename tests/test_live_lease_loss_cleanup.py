"""Live lease-loss cleanup using actual children, pipes and persisted leases.

Python children stand in for upstream/ffmpeg; no provider/media conversion claim.
"""

import asyncio
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


from app.database import Base
from app.models import TwitchUpstreamLease
from app.services.live_streaming_service import LiveStreamSession, LiveStreamingService
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest_asyncio.fixture
async def live(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'live-leases.db'}",
        connect_args={"check_same_thread": False},
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
@pytest.mark.parametrize("recovery", [None, "stop", "shutdown"])
async def test_heartbeat_loss_reaps_owned_children_and_pipe(
    live, reason, recovery, monkeypatch
):
    service, session, coordinator, factory, spawn, pipe = live
    session.user_id = "956"
    service.user_sessions["956"] = {session.session_id}
    inspect = coordinator.inspect_process_identity
    sink_record = service._supervisor.get_process(f"{session.session_id}:ffmpeg")
    if recovery:
        import psutil

        # EOF must not hide failed cleanup of our still-live sink.
        os.kill(session.ffmpeg_process.pid, signal.SIGSTOP)
        async with asyncio.timeout(3):
            while (
                psutil.Process(session.ffmpeg_process.pid).status()
                != psutil.STATUS_STOPPED
            ):
                await asyncio.sleep(0.01)

        async def unavailable_identity(pid):
            if pid == session.ffmpeg_process.pid:
                raise OSError("controlled temporary sink identity lookup failure")
            return await inspect(pid)

        monkeypatch.setattr(
            coordinator, "inspect_process_identity", unavailable_identity
        )
    replacement = None
    if reason == "replacement":
        replacement = await spawn("import time;time.sleep(60)")
        identity = await coordinator.inspect_process_identity(replacement.pid)
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        lease.owner_user_id = 956
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
    if recovery:
        for _ in range(2):
            assert not session.is_active
            assert session.ffmpeg_process.returncode is None
            assert service.sessions[session.session_id] is session
            assert session.session_id in service.user_sessions["956"]
            assert session.output_dir.exists()
            assert (
                service._supervisor.get_process(f"{session.session_id}:ffmpeg")
                is sink_record
            )
            assert pipe.done()
            with factory() as db:
                assert list(db.execute(select(TwitchUpstreamLease.__table__))) == before
            await service._monitor_session(session.session_id)
        monkeypatch.setattr(coordinator, "inspect_process_identity", inspect)
        if recovery == "stop":
            assert await asyncio.wait_for(service.stop_stream(session.session_id), 8)
        else:
            await asyncio.wait_for(service.stop(), 8)
    assert session.streamlink_process.returncode is not None
    assert session.ffmpeg_process.returncode is not None
    assert pipe.done()
    assert service._supervisor.process_names == ()
    assert session.session_id not in service.sessions
    assert session.session_id not in service.user_sessions["956"]
    assert not session.output_dir.exists()
    assert await service.stop_stream(session.session_id) is False
    await service.stop()
    await service.stop()
    if replacement:
        assert replacement.returncode is None
    with factory() as db:
        assert (
            list(db.execute(select(TwitchUpstreamLease.__table__)).tuples()) == before
        )


@pytest.mark.asyncio
async def test_live_fixture_uses_distinct_connections_for_concurrent_transactions(live):
    _, _, _, factory, _, _ = live
    with factory() as first:
        original = first.connection().connection.driver_connection

        def another_transaction():
            with factory() as second:
                return second.connection().connection.driver_connection is original

        assert await asyncio.to_thread(another_transaction) is False


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
    "protection",
    [
        "fingerprint_mismatch",
        "replacement_adopts_same_process",
        "authorization_unavailable",
        "identity_unavailable",
    ],
)
async def test_lease_loss_never_signals_foreign_identity_but_cleans_local_sink(
    live, protection, monkeypatch
):
    service, session, _, factory, _, pipe = live
    session.user_id = "956"
    service.user_sessions["956"] = {session.session_id}
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        lease.owner_user_id = 956
        if protection == "replacement_adopts_same_process":
            lease.generation = 2
            lease.live_session_id = "replacement956"
        else:
            lease.state = "RELEASED"
            if protection == "fingerprint_mismatch":
                session.process_start_fingerprint = "not-the-child-fingerprint"
        db.commit()
        before = list(db.execute(select(TwitchUpstreamLease.__table__)).tuples())
    if protection == "authorization_unavailable":

        async def unavailable(**kwargs):
            raise OSError("controlled authorization read failure")

        monkeypatch.setattr(
            service._coordinator, "assert_local_process_cleanup_authorized", unavailable
        )
    elif protection == "identity_unavailable":
        inspect = service._coordinator.inspect_process_identity

        async def unavailable_identity(pid):
            if pid == session.streamlink_process.pid:
                raise ProcessLookupError("controlled native identity lookup failure")
            return await inspect(pid)

        monkeypatch.setattr(
            service._coordinator, "inspect_process_identity", unavailable_identity
        )
    await asyncio.wait_for(service._monitor_session(session.session_id), 3)
    assert session.streamlink_process.returncode is None
    assert session.ffmpeg_process.returncode is not None
    assert pipe.done()
    assert not session.is_active
    assert session.session_id not in service.sessions
    assert session.session_id not in service.user_sessions["956"]
    assert not session.output_dir.exists()
    assert service._supervisor.process_names == ()
    assert service._supervisor.task_names == ()
    await service._monitor_session(session.session_id)
    assert await service.stop_stream(session.session_id) is False
    await service.stop()
    await service.stop()
    assert session.streamlink_process.returncode is None
    with factory() as db:
        assert (
            list(db.execute(select(TwitchUpstreamLease.__table__)).tuples()) == before
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "active,error_type",
    [(True, OSError), (True, asyncio.CancelledError), (False, asyncio.CancelledError)],
)
async def test_aborted_authorization_preserves_capture_and_previous_activity(
    live, monkeypatch, active, error_type
):
    service, session, coordinator, factory, _, pipe = live
    session.is_active = active
    with factory() as db:
        before = list(db.execute(select(TwitchUpstreamLease.__table__)))

    async def abort(**kwargs):
        raise error_type("controlled aborted authorization")

    method = (
        "assert_stop_authorized"
        if active
        else "assert_local_process_cleanup_authorized"
    )
    monkeypatch.setattr(coordinator, method, abort)
    with pytest.raises(error_type):
        await service.stop_stream(session.session_id)
    assert session.is_active is active
    assert service.sessions[session.session_id] is session
    assert session.streamlink_process.returncode is None
    assert session.ffmpeg_process.returncode is None and not pipe.done()
    assert set(service._supervisor.process_names) == {
        "owned956:streamlink",
        "owned956:ffmpeg",
    }
    assert (
        session.output_dir / "fragment.ts"
    ).read_bytes() == b"owned synthetic fragment"
    with factory() as db:
        assert list(db.execute(select(TwitchUpstreamLease.__table__))) == before


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
@pytest.mark.parametrize("media", ["python", "ffmpeg"])
@pytest.mark.parametrize("cleanup", ["heartbeat", "shutdown"])
async def test_native_started_service_shutdown_preserves_replacement_owner(
    image_applications, monkeypatch, media, cleanup
):
    from app import dependencies
    from app.lifespan import _close_application_proxy, _close_application_twitch

    applications, databases, _, _ = image_applications
    app = applications[0]
    service = dependencies._get_application_live_streaming_service(app)
    assert app.state.live_streaming_service is service
    assert service._coordinator is app.state.recording_manager._upstream_coordinator
    factory = databases[0].sync_session_factory
    if media == "python":
        monkeypatch.setenv("FFMPEG_PATH", sys.executable)

    async def upstream_command(*args, **kwargs):
        if media == "ffmpeg":
            return [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-re",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=64x64:rate=10",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-g",
                "10",
                "-f",
                "mpegts",
                "pipe:1",
            ]
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
    if media == "python":
        monkeypatch.setattr(service, "_build_ffmpeg_command", sink_command)
    result = await service._start_stream_once("native956")
    session = service.sessions[result.session_id]
    assert session.playlist_path.read_bytes().startswith(b"#EXTM3U")
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
        if cleanup == "heartbeat":
            await service._monitor_session(session.session_id)
            assert session.session_id not in service.sessions
            assert service._supervisor.process_names == ()
            assert not session.output_dir.exists()
        await service.stop()
        assert session.streamlink_process.returncode is None
        assert session.ffmpeg_process.returncode is not None
        assert service._supervisor.task_names == ()
        assert service._supervisor.process_names == ()
        assert session.session_id not in service.sessions
        assert not session.output_dir.exists()
        assert await service.stop_stream(session.session_id) is False
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
        await service.stop()
        await _close_application_proxy(app)
        await _close_application_twitch(app)
        await app.state.recording_manager.process_manager.cleanup_all()
        await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()


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


@pytest.mark.asyncio
async def test_local_peer_adoption_protects_pid_without_releasing_lease(live):
    service, stale, _, factory, spawn, pipe = live
    peer_sink = await spawn("import time;time.sleep(60)")
    peer_output = stale.output_dir.parent / "peer-live"
    peer_output.mkdir()
    (peer_output / "fragment.ts").write_bytes(b"peer fragment")
    peer = LiveStreamSession(
        "peer956",
        "peer",
        "best",
        stale.streamlink_process,
        peer_sink,
        peer_output,
        user_id="957",
        lease_generation=2,
    )
    service.sessions[peer.session_id] = peer
    service.user_sessions[peer.user_id] = {peer.session_id}
    service._supervisor.track_process("peer956:streamlink", peer.streamlink_process)
    service._supervisor.track_process("peer956:ffmpeg", peer_sink)
    protected = {
        name: record
        for name, record in service._supervisor._processes.items()
        if name.startswith("peer956:")
    }
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        lease.state = "RELEASED"
        db.commit()
        before = list(db.execute(select(TwitchUpstreamLease.__table__)))
    await service._monitor_session(stale.session_id)
    assert service.sessions == {peer.session_id: peer}
    assert service.user_sessions[peer.user_id] == {peer.session_id}
    assert stale.streamlink_process.returncode is None
    assert peer_sink.returncode is None
    assert stale.ffmpeg_process.returncode is not None and pipe.done()
    assert not stale.output_dir.exists()
    assert (peer_output / "fragment.ts").read_bytes() == b"peer fragment"
    assert set(service._supervisor.process_names) == set(protected)
    assert all(
        service._supervisor.get_process(name) is record
        for name, record in protected.items()
    )
    with factory() as db:
        assert list(db.execute(select(TwitchUpstreamLease.__table__))) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("generation", [1, 2])
@pytest.mark.parametrize("adopts_upstream", [False, True])
@pytest.mark.parametrize("replacement_user", ["956", "957"])
@pytest.mark.parametrize("pause_at", ["authorization", "dispatch"])
async def test_overlapping_fenced_cleanup_preserves_replacement_resources(
    live, monkeypatch, generation, adopts_upstream, replacement_user, pause_at
):
    service, stale, coordinator, factory, spawn, pipe = live
    stale.user_id = "956"
    service.user_sessions["956"] = {stale.session_id}
    replacement_upstream = (
        stale.streamlink_process
        if adopts_upstream
        else await spawn("import time;time.sleep(60)")
    )
    replacement_sink = await spawn("import time;time.sleep(60)")
    replacement = LiveStreamSession(
        stale.session_id,
        "replacement",
        "best",
        replacement_upstream,
        replacement_sink,
        stale.output_dir,
        user_id=replacement_user,
        channel_key=stale.channel_key,
        lease_generation=generation,
    )
    identity = await coordinator.inspect_process_identity(replacement_upstream.pid)
    with factory() as db:
        lease = db.scalar(select(TwitchUpstreamLease))
        lease.generation = generation
        lease.live_session_id = stale.session_id
        lease.owner_user_id = int(replacement_user)
        lease.process_pid = identity.pid
        lease.process_group_id = identity.process_group_id
        lease.process_started_at = identity.started_at
        lease.process_start_fingerprint = identity.fingerprint
        db.commit()
        before = list(db.execute(select(TwitchUpstreamLease.__table__)))
    entered, proceed = asyncio.Event(), asyncio.Event()
    original = coordinator.assert_local_process_cleanup_authorized

    async def authorize(**kwargs):
        entered.set()
        await proceed.wait()
        return await original(**kwargs)

    if pause_at == "authorization":
        monkeypatch.setattr(
            coordinator, "assert_local_process_cleanup_authorized", authorize
        )
    else:
        finish = service._finish_session_stop

        async def dispatch(*args, **kwargs):
            entered.set()
            await proceed.wait()
            return await finish(*args, **kwargs)

        monkeypatch.setattr(service, "_finish_session_stop", dispatch)
    stale.is_active = False
    stopping = asyncio.create_task(service.stop_stream(stale.session_id))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        async with service._lock:
            service.sessions[stale.session_id] = replacement
            service.user_sessions[replacement_user] = {stale.session_id}
            # Simulate the new owner's published records under the same names.
            for label, process in (
                ("streamlink", replacement_upstream),
                ("ffmpeg", replacement_sink),
            ):
                service._supervisor.track_process(f"replacement:{label}", process)
                service._supervisor._processes[f"{stale.session_id}:{label}"] = (
                    service._supervisor._processes.pop(f"replacement:{label}")
                )
            new_task = service._supervisor.create_task(
                "replacement:media-pipe", asyncio.Event().wait()
            )
            service._supervisor._tasks[f"{stale.session_id}:media-pipe"] = (
                service._supervisor._tasks.pop("replacement:media-pipe")
            )
        protected_records = dict(service._supervisor._processes)
        protected_state = vars(replacement).copy()
        files_before = {
            p.name: p.read_bytes() for p in replacement.output_dir.iterdir()
        }
        proceed.set()
        await asyncio.wait({stopping}, timeout=3)
        assert stopping.done(), "stale cleanup waited on the replacement's child"
        assert await stopping is True
        assert service.sessions[stale.session_id] is replacement
        assert vars(replacement) == protected_state
        assert service.user_sessions[replacement_user] == {stale.session_id}
        if replacement_user != stale.user_id:
            assert service.user_sessions[stale.user_id] == set()
        assert replacement_upstream.returncode is None
        assert replacement_sink.returncode is None
        assert (stale.streamlink_process.returncode is None) is adopts_upstream
        assert stale.ffmpeg_process.returncode is not None
        assert pipe.done()
        assert not new_task.done()
        assert service._supervisor._processes == protected_records
        assert {
            p.name: p.read_bytes() for p in replacement.output_dir.iterdir()
        } == files_before
        with factory() as db:
            assert list(db.execute(select(TwitchUpstreamLease.__table__))) == before
    finally:
        proceed.set()
        if not stopping.done():
            for child in (
                stale.streamlink_process,
                stale.ffmpeg_process,
                replacement_upstream,
                replacement_sink,
            ):
                if child.returncode is None:
                    child.kill()
                await child.wait()
        await asyncio.gather(stopping, return_exceptions=True)
        monkeypatch.setattr(
            coordinator, "assert_local_process_cleanup_authorized", original
        )
