"""
Tests for the Live Streaming Service without external services.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_live_stream_session_properties():
    """Test LiveStreamSession basic properties and expiration"""
    from app.services.live_streaming_service import LiveStreamSession

    session = LiveStreamSession(
        session_id="abc123",
        streamer_name="test_streamer",
        quality="best",
        streamlink_process=MagicMock(),
        ffmpeg_process=MagicMock(),
        output_dir=MagicMock(),
    )

    assert session.session_id == "abc123"
    assert session.streamer_name == "test_streamer"
    assert session.quality == "best"
    assert session.is_active is True
    assert session.playback_token
    assert session.validate_playback_token(session.playback_token) is True
    assert session.validate_playback_token("wrong-token") is False
    assert session.validate_playback_token(None) is False

    # Fresh session not expired
    assert session.is_expired(timeout_seconds=60) is False

    # Simulate old session
    session.last_accessed = datetime.utcnow() - timedelta(seconds=120)
    assert session.is_expired(timeout_seconds=60) is True


def test_live_stream_session_touch():
    """Test touch() updates last_accessed"""
    from app.services.live_streaming_service import LiveStreamSession

    session = LiveStreamSession(
        session_id="abc123",
        streamer_name="test",
        quality="720p60",
        streamlink_process=MagicMock(),
        ffmpeg_process=MagicMock(),
        output_dir=MagicMock(),
    )

    old_accessed = session.last_accessed
    session.touch()
    assert session.last_accessed > old_accessed


def test_live_streaming_service_init():
    """Test service initialization"""
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    assert svc.SESSION_TIMEOUT_SECONDS == 60
    assert svc.MAX_CONCURRENT_STREAMS == 5
    assert svc.HLS_SEGMENT_DURATION == 2
    assert svc.HLS_LIST_SIZE == 10
    assert svc.sessions == {}
    assert svc.user_sessions == {}


def test_normalize_supported_codecs_for_live_playback():
    """Test live codec normalization keeps recordings config out of live playback."""
    from app.services.live_streaming_service import LiveStreamingService

    assert LiveStreamingService._normalize_supported_codecs("h264") == "h264"
    assert LiveStreamingService._normalize_supported_codecs("h264,h265") == "h264,h265"
    assert (
        LiveStreamingService._normalize_supported_codecs(" h265 , h264 ") == "h265,h264"
    )
    assert (
        LiveStreamingService._normalize_supported_codecs("h264,h264,h265")
        == "h264,h265"
    )
    assert LiveStreamingService._normalize_supported_codecs("vp9,unknown") == "h264"
    assert LiveStreamingService._normalize_supported_codecs("") == "h264"


def test_append_playback_token_to_playlist():
    """Test live playlist segment URIs receive playback tokens."""
    from app.routes.live import _append_playback_token_to_playlist

    playlist = "#EXTM3U\n#EXTINF:2.0,\nsegment_000.ts\nsegment_001.ts?range=1\n"

    rewritten = _append_playback_token_to_playlist(playlist, "abc+/=")

    assert "#EXTM3U" in rewritten
    assert "segment_000.ts?token=abc%2B%2F%3D" in rewritten
    assert "segment_001.ts?range=1&token=abc%2B%2F%3D" in rewritten
    assert rewritten.endswith("\n")


def test_build_ffmpeg_command_structure():
    """Test FFmpeg command contains required arguments"""
    from app.services.live_streaming_service import LiveStreamingService
    from pathlib import Path

    svc = LiveStreamingService()
    output_dir = Path("/tmp/test-live")
    cmd = svc._build_ffmpeg_command(output_dir)

    assert cmd[0] == "ffmpeg"
    assert "-hide_banner" in cmd
    assert "-" in cmd  # stdin
    assert "-c" in cmd
    assert "copy" in cmd
    assert "-f" in cmd
    assert "hls" in cmd
    assert "-hls_time" in cmd
    assert "-hls_list_size" in cmd
    assert "-hls_flags" in cmd
    assert "delete_segments+omit_endlist" in cmd
    assert "-hls_segment_filename" in cmd
    assert str(output_dir / "playlist.m3u8") in cmd


def test_get_session_not_found():
    """Test get_session returns None for unknown session"""
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    assert svc.get_session("nonexistent") is None


def test_get_session_status_not_found():
    """Test get_session_status returns None for unknown session"""
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    assert svc.get_session_status("nonexistent") is None


def test_stop_stream_not_found():
    """Test stop_stream returns False for unknown session"""
    import asyncio
    from app.services.live_streaming_service import LiveStreamingService

    svc = LiveStreamingService()
    result = asyncio.run(svc.stop_stream("nonexistent"))
    assert result is False


def test_stop_existing_user_streams_replaces_same_streamer():
    """Test replacement cleanup only stops matching user/streamer sessions."""
    import asyncio
    from app.services.live_streaming_service import (
        LiveStreamingService,
        LiveStreamSession,
    )

    svc = LiveStreamingService()

    def make_session(session_id: str, streamer_name: str, user_id: str):
        streamlink_process = MagicMock()
        streamlink_process.returncode = 0
        ffmpeg_process = MagicMock()
        ffmpeg_process.returncode = 0
        output_dir = MagicMock()
        output_dir.exists.return_value = False
        return LiveStreamSession(
            session_id=session_id,
            streamer_name=streamer_name,
            quality="best",
            streamlink_process=streamlink_process,
            ffmpeg_process=ffmpeg_process,
            output_dir=output_dir,
            user_id=user_id,
        )

    svc.sessions = {
        "old": make_session("old", "HandOfBlood", "user-1"),
        "other-streamer": make_session("other-streamer", "maxim", "user-1"),
        "other-user": make_session("other-user", "HandOfBlood", "user-2"),
    }
    svc.user_sessions = {"user-1": {"old", "other-streamer"}, "user-2": {"other-user"}}

    asyncio.run(svc._stop_existing_user_streams("user-1", "handofblood"))

    assert "old" not in svc.sessions
    assert "old" not in svc.user_sessions["user-1"]
    assert "other-streamer" in svc.sessions
    assert "other-user" in svc.sessions


def test_live_proxy_command_preserves_url_and_redacts_diagnostics(monkeypatch, caplog):
    from app.services import live_streaming_service

    proxy_url = (
        "https://live-user:live-password@proxy.example:8443/"
        "signed/path?token=live-secret#live-fragment"
    )

    class TokenService:
        def __init__(self, db):
            pass

        async def get_valid_access_token(self):
            return None

    async def get_best_proxy():
        return proxy_url

    monkeypatch.setattr(live_streaming_service, "TwitchTokenService", TokenService)
    monkeypatch.setattr(
        live_streaming_service.proxy_health_service,
        "get_best_proxy",
        get_best_proxy,
    )

    service = live_streaming_service.LiveStreamingService()
    with caplog.at_level(logging.DEBUG, logger="streamvault"):
        command = asyncio.run(service._build_streamlink_command("streamer", "best"))

    assert f"--http-proxy={proxy_url}" in command
    assert "proxy.example:8443" in caplog.text
    for secret in (
        "live-user",
        "live-password",
        "signed",
        "path",
        "token",
        "live-secret",
        "live-fragment",
    ):
        assert secret not in caplog.text


def test_live_proxy_lookup_exception_does_not_reach_diagnostics(monkeypatch, caplog):
    from app.services import live_streaming_service

    proxy_url = (
        "https://live-user:live-password@proxy.example:8443/"
        "signed/path?token=live-secret#live-fragment"
    )

    class TokenService:
        def __init__(self, db):
            pass

        async def get_valid_access_token(self):
            return None

    async def get_best_proxy():
        raise RuntimeError(proxy_url)

    monkeypatch.setattr(live_streaming_service, "TwitchTokenService", TokenService)
    monkeypatch.setattr(
        live_streaming_service.proxy_health_service,
        "get_best_proxy",
        get_best_proxy,
    )

    service = live_streaming_service.LiveStreamingService()
    with caplog.at_level(logging.WARNING, logger="streamvault"):
        command = asyncio.run(service._build_streamlink_command("streamer", "best"))

    assert not any(arg.startswith("--http-proxy=") for arg in command)
    assert "Could not get proxy" in caplog.text
    assert proxy_url not in caplog.text


def test_anonymous_live_does_not_request_twitch_token(monkeypatch):
    from app.services import live_streaming_service

    class ForbiddenTokenService:
        def __init__(self, db):
            raise AssertionError("anonymous Live requested a Twitch token")

    async def no_proxy():
        return None

    monkeypatch.setattr(
        live_streaming_service, "TwitchTokenService", ForbiddenTokenService
    )
    monkeypatch.setattr(
        live_streaming_service.proxy_health_service, "get_best_proxy", no_proxy
    )

    service = live_streaming_service.LiveStreamingService()
    command = asyncio.run(
        service._build_streamlink_command(
            "streamer", "best", supported_codecs="h264,h265"
        )
    )

    assert not any(argument.startswith("--twitch-api-header=") for argument in command)


def test_enhanced_live_requests_twitch_token_explicitly(monkeypatch):
    from app.services import live_streaming_service

    calls = []

    class TokenService:
        def __init__(self, db):
            calls.append("created")

        async def get_valid_access_token(self):
            calls.append("requested")
            return "local-test-token"

    async def no_proxy():
        return None

    monkeypatch.setattr(live_streaming_service, "TwitchTokenService", TokenService)
    monkeypatch.setattr(
        live_streaming_service.proxy_health_service, "get_best_proxy", no_proxy
    )

    service = live_streaming_service.LiveStreamingService()
    command = asyncio.run(
        service._build_streamlink_command(
            "streamer",
            "best",
            supported_codecs="h264",
            enhanced_quality=True,
        )
    )

    assert calls == ["created", "requested"]
    assert any(argument.startswith("--twitch-api-header=") for argument in command)


@pytest.mark.asyncio
async def test_live_streamlink_stderr_is_sanitized_and_context_is_released(caplog):
    from app.services.live_streaming_service import LiveStreamingService

    class Stderr:
        def __init__(self):
            self.lines = [
                b"Authorization=OAuth fixture-auth-value-807 ",
                b"https://viewer:fixture-pass@relay.example:8443/path\n",
                b"",
            ]

        async def readline(self):
            return self.lines.pop(0)

    class Process:
        def __init__(self):
            self.stderr = Stderr()

    process = Process()
    service = LiveStreamingService()
    service._streamlink_output_secrets[process] = ("fixture-auth-value-807",)

    with caplog.at_level(logging.DEBUG, logger="streamvault"):
        await service._log_stderr(process, "streamlink-local")

    assert process not in service._streamlink_output_secrets
    assert "relay.example:8443" in caplog.text
    for value in ("viewer", "fixture-pass", "fixture-auth-value-807"):
        assert value not in caplog.text


@pytest.mark.asyncio
async def test_live_reserves_before_children_and_releases_on_cancellation(
    monkeypatch, tmp_path
):
    from app.services import live_streaming_service

    calls = []
    activated = asyncio.Event()
    playlist_wait = asyncio.Event()

    class Coordinator:
        async def reserve(self, **values):
            calls.append(("reserve", values))
            return SimpleNamespace(
                channel_key=values["channel_key"],
                generation=1,
                live_session_id=values["live_session_id"],
            )

        async def activate(self, **values):
            calls.append(("activate", values))
            activated.set()
            return SimpleNamespace(
                process_group_id=values["process_group_id"],
                process_started_at=datetime.utcnow(),
                process_start_fingerprint="birth-302",
            )

        async def assert_stop_authorized(self, **values):
            calls.append(("authorize-stop", values))

        async def inspect_process_identity(self, process_pid):
            from app.services.twitch_upstream_coordinator import ProcessIdentity

            return ProcessIdentity(
                process_pid,
                process_pid,
                datetime.utcnow(),
                f"birth-{process_pid}",
            )

        async def release(self, **values):
            calls.append(("release", values))
            return True

    class Process:
        def __init__(self, pid):
            self.pid = pid
            self.returncode = None
            self.stdout = None
            self.stderr = None
            self.stdin = None
            self.terminate_calls = 0
            self.kill_calls = 0

        def terminate(self):
            self.terminate_calls += 1
            self.returncode = -15

        def kill(self):
            self.kill_calls += 1
            self.returncode = -9

        async def wait(self):
            return self.returncode

    processes = [Process(301), Process(302)]
    subprocess_kwargs = []

    async def create_subprocess(*args, **kwargs):
        assert calls and calls[0][0] == "reserve"
        subprocess_kwargs.append(kwargs)
        return processes[len(subprocess_kwargs) - 1]

    async def wait_for_playlist(*args, **kwargs):
        await playlist_wait.wait()
        return True

    async def command(*args, **kwargs):
        return ["local-streamlink-fixture"]

    monkeypatch.setattr(live_streaming_service.shutil, "which", lambda path: path)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess)
    monkeypatch.setattr(live_streaming_service.os, "getpgid", lambda pid: pid)

    def kill_process_group(process_group_id, sig):
        process = next(
            process for process in processes if process.pid == process_group_id
        )
        process.returncode = -sig

    monkeypatch.setattr(live_streaming_service.os, "killpg", kill_process_group)

    service = live_streaming_service.LiveStreamingService(
        coordinator=Coordinator(), output_root=tmp_path
    )
    service._wait_for_playlist = wait_for_playlist
    service._build_streamlink_command = command

    start = asyncio.create_task(
        service.start_stream(
            streamer_name="streamer",
            channel_key="stable-channel-id",
            user_id="7",
        )
    )
    await activated.wait()
    start.cancel()

    with pytest.raises(asyncio.CancelledError):
        await start

    assert [name for name, _values in calls] == [
        "reserve",
        "activate",
        "authorize-stop",
        "release",
    ]
    assert all(options["start_new_session"] is True for options in subprocess_kwargs)
    assert all(process.returncode is not None for process in processes)


@pytest.mark.asyncio
async def test_compatible_duplicate_joins_in_flight_live_start(monkeypatch, tmp_path):
    from app.services import live_streaming_service
    from app.services.twitch_upstream_coordinator import (
        ProcessIdentity,
        TwitchUpstreamConflict,
    )

    reservations = []
    first_session_id = None
    playlist_waiting = asyncio.Event()
    playlist_ready = asyncio.Event()

    class Coordinator:
        async def reserve(self, **values):
            nonlocal first_session_id
            reservations.append(values)
            if first_session_id is None:
                first_session_id = values["live_session_id"]
            elif values["auth_key"] is not None:
                raise TwitchUpstreamConflict(
                    "twitch_upstream_live_policy_conflict",
                    "live_policy_mismatch",
                    values["channel_key"],
                )
            return SimpleNamespace(
                channel_key=values["channel_key"],
                generation=1,
                live_session_id=first_session_id,
            )

        async def activate(self, **values):
            return SimpleNamespace(
                process_group_id=values["process_group_id"],
                process_started_at=datetime.now(timezone.utc),
                process_start_fingerprint=f"birth-{values['process_pid']}",
            )

        async def inspect_process_identity(self, process_pid):
            return ProcessIdentity(
                process_pid,
                process_pid,
                datetime.now(timezone.utc),
                f"birth-{process_pid}",
            )

        async def assert_stop_authorized(self, **values):
            return None

        async def release(self, **values):
            return True

    class Process:
        def __init__(self, pid):
            self.pid = pid
            self.returncode = None
            self.stdout = None
            self.stderr = None
            self.stdin = None

        async def wait(self):
            return self.returncode

    processes = [Process(401), Process(402)]
    subprocess_calls = []

    async def create_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        return processes[len(subprocess_calls) - 1]

    async def command(*args, **kwargs):
        return ["local-streamlink-fixture"]

    async def wait_for_playlist(*args, **kwargs):
        playlist_waiting.set()
        await playlist_ready.wait()
        return True

    async def monitor(*args, **kwargs):
        return None

    monkeypatch.setattr(live_streaming_service.shutil, "which", lambda path: path)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess)
    service = live_streaming_service.LiveStreamingService(
        coordinator=Coordinator(), output_root=tmp_path
    )
    service._build_streamlink_command = command
    service._wait_for_playlist = wait_for_playlist
    service._monitor_session = monitor

    first = asyncio.create_task(
        service.start_stream(
            streamer_name="streamer",
            channel_key="stable-channel-id",
            user_id="7",
        )
    )
    await playlist_waiting.wait()
    duplicate = asyncio.create_task(
        service.start_stream(
            streamer_name="streamer",
            channel_key="stable-channel-id",
            user_id="7",
        )
    )
    await asyncio.sleep(0)
    assert not duplicate.done()

    with pytest.raises(TwitchUpstreamConflict) as policy:
        await service.start_stream(
            streamer_name="streamer",
            channel_key="stable-channel-id",
            user_id="7",
            enhanced_quality=True,
        )
    assert policy.value.code == "twitch_upstream_live_policy_conflict"

    playlist_ready.set()
    first_result, duplicate_result = await asyncio.gather(first, duplicate)

    assert first_result.idempotent is False
    assert duplicate_result.idempotent is True
    assert duplicate_result.session_id == first_result.session_id
    assert service.get_session(first_result.session_id) is not None
    assert len(subprocess_calls) == 2
    assert len(reservations) == 2


@pytest.mark.asyncio
async def test_live_activation_failure_reaps_exact_children_before_durable_release(
    monkeypatch, tmp_path
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import (
        GlobalSettings,
        TwitchUpstreamCoordinationState,
        TwitchUpstreamLease,
    )
    from app.services import live_streaming_service
    from app.services.twitch_upstream_coordinator import (
        ProcessIdentity,
        TwitchUpstreamCoordinator,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'live-activation-failure.db'}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(
        engine,
        tables=[
            TwitchUpstreamCoordinationState.__table__,
            TwitchUpstreamLease.__table__,
            GlobalSettings.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    started_at = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    class Inspector:
        def inspect(self, pid):
            return ProcessIdentity(pid, pid + 1000, started_at, f"birth-{pid}")

        def is_exact_process_alive(self, **identity):
            return True

    class Process:
        def __init__(self, pid):
            self.pid = pid
            self.returncode = None
            self.stdout = None
            self.stderr = None
            self.stdin = None

        async def wait(self):
            return self.returncode

    coordinator = TwitchUpstreamCoordinator(
        Session,
        monotonic_clock=lambda: 1.0,
        process_inspector=Inspector(),
    )
    activation_values = []

    async def fail_activation(**values):
        activation_values.append(values)
        raise RuntimeError("injected activation failure")

    coordinator.activate = fail_activation
    processes = [Process(301), Process(302)]
    subprocess_calls = []

    async def create_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        return processes[len(subprocess_calls) - 1]

    async def command(*args, **kwargs):
        return ["local-streamlink-fixture"]

    signaled = []

    def kill_process_group(process_group_id, sig):
        signaled.append((process_group_id, sig))
        process = next(
            process for process in processes if process.pid + 1000 == process_group_id
        )
        process.returncode = -sig

    original_release = coordinator.release
    release_observations = []

    async def release_after_reap(**values):
        release_observations.append(
            (
                values,
                tuple(process.returncode for process in processes),
                tuple(signaled),
            )
        )
        return await original_release(**values)

    coordinator.release = release_after_reap
    monkeypatch.setattr(live_streaming_service.shutil, "which", lambda path: path)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess)
    monkeypatch.setattr(live_streaming_service.os, "killpg", kill_process_group)

    service = live_streaming_service.LiveStreamingService(
        coordinator=coordinator, output_root=tmp_path / "live"
    )
    service._build_streamlink_command = command

    with pytest.raises(RuntimeError, match="injected activation failure"):
        await service.start_stream(
            streamer_name="streamer",
            channel_key="live-activation-channel",
            user_id="7",
        )

    assert len(subprocess_calls) == 2
    assert activation_values == [
        {
            "channel_key": "live-activation-channel",
            "generation": 1,
            "process_pid": 302,
            "process_group_id": 1302,
            "process_started_at": started_at,
            "process_start_fingerprint": "birth-302",
        }
    ]
    assert release_observations == [
        (
            {
                "channel_key": "live-activation-channel",
                "generation": 1,
                "reason": "live_start_failed",
            },
            (-15, -15),
            (
                (1302, live_streaming_service.signal.SIGTERM),
                (1301, live_streaming_service.signal.SIGTERM),
            ),
        )
    ]
    with Session() as db:
        lease = db.query(TwitchUpstreamLease).one()
        assert (lease.state, lease.release_reason) == (
            "RELEASED",
            "live_start_failed",
        )
    engine.dispose()


@pytest.mark.asyncio
async def test_live_stop_requires_persisted_live_owner_before_signaling(tmp_path):
    from app.services.live_streaming_service import (
        LiveStreamSession,
        LiveStreamingService,
        TwitchUpstreamStopForbidden,
    )

    calls = []

    class Coordinator:
        async def assert_stop_authorized(self, **values):
            calls.append(("authorize", values))
            raise PermissionError("durable owner mismatch")

        async def release(self, **values):
            calls.append(("release", values))
            return True

    streamlink_process = SimpleNamespace(pid=701, returncode=None)
    ffmpeg_process = SimpleNamespace(pid=702, returncode=None)
    session = LiveStreamSession(
        session_id="session-7",
        streamer_name="streamer",
        quality="best",
        streamlink_process=streamlink_process,
        ffmpeg_process=ffmpeg_process,
        output_dir=tmp_path,
        user_id="7",
        channel_key="live-stop-channel",
        lease_generation=3,
        process_group_id=701,
        process_start_fingerprint="birth-701",
        ffmpeg_process_group_id=702,
        ffmpeg_process_start_fingerprint="birth-702",
    )
    service = LiveStreamingService(coordinator=Coordinator(), output_root=tmp_path)
    service.sessions[session.session_id] = session
    service.user_sessions = {"7": {session.session_id}}

    async def forbidden_reap(process):
        raise AssertionError("unauthorized process was signaled")

    service._reap_process = forbidden_reap

    with pytest.raises(TwitchUpstreamStopForbidden):
        await service.stop_stream(session.session_id, requesting_user_id="7")

    assert calls == [
        (
            "authorize",
            {
                "channel_key": "live-stop-channel",
                "generation": 3,
                "process_pid": 701,
                "process_group_id": 701,
                "process_start_fingerprint": "birth-701",
                "expected_purpose": "LIVE",
                "requesting_owner_user_id": 7,
            },
        )
    ]
    assert session.is_active is True


@pytest.mark.asyncio
async def test_live_monitor_releases_dead_leader_without_signaling_reused_pid(
    monkeypatch, tmp_path
):
    from app.services import live_streaming_service
    from app.services.live_streaming_service import (
        LiveStreamSession,
        LiveStreamingService,
    )

    calls = []

    class Coordinator:
        async def heartbeat(self, **values):
            calls.append(("heartbeat", values))
            return True

        async def assert_stop_authorized(self, **values):
            raise AssertionError("dead leader used the manual stop authorization path")

        async def assert_exited_process_cleanup_authorized(self, **values):
            calls.append(("authorize-exited-cleanup", values))

        async def inspect_process_identity(self, process_pid):
            from app.services.twitch_upstream_coordinator import ProcessIdentity

            return ProcessIdentity(
                process_pid,
                process_pid,
                datetime.utcnow(),
                f"birth-{process_pid}",
            )

        async def release(self, **values):
            calls.append(("release", values))
            return True

    class Process:
        def __init__(self, pid, returncode):
            self.pid = pid
            self.returncode = returncode
            self.kill_calls = 0

        def kill(self):
            self.kill_calls += 1
            self.returncode = -9

        async def wait(self):
            return self.returncode

    streamlink_process = Process(701, 1)
    ffmpeg_process = Process(702, None)
    session = LiveStreamSession(
        session_id="session-7",
        streamer_name="streamer",
        quality="best",
        streamlink_process=streamlink_process,
        ffmpeg_process=ffmpeg_process,
        output_dir=tmp_path,
        user_id="7",
        channel_key="live-monitor-channel",
        lease_generation=3,
        process_group_id=701,
        process_start_fingerprint="birth-701",
        ffmpeg_process_group_id=702,
        ffmpeg_process_start_fingerprint="birth-702",
    )
    service = LiveStreamingService(coordinator=Coordinator(), output_root=tmp_path)
    service.sessions[session.session_id] = session
    service.user_sessions = {"7": {session.session_id}}

    signaled_process_groups = []

    def kill_process_group(process_group_id, sig):
        signaled_process_groups.append(process_group_id)
        if process_group_id == ffmpeg_process.pid:
            ffmpeg_process.returncode = -sig

    monkeypatch.setattr(
        live_streaming_service.os, "getpgid", lambda process_id: process_id
    )
    monkeypatch.setattr(live_streaming_service.os, "killpg", kill_process_group)

    await service._monitor_session(session.session_id)

    assert calls == [
        (
            "heartbeat",
            {"channel_key": "live-monitor-channel", "generation": 3},
        ),
        (
            "authorize-exited-cleanup",
            {
                "channel_key": "live-monitor-channel",
                "generation": 3,
                "process_pid": 701,
                "process_group_id": 701,
                "process_start_fingerprint": "birth-701",
                "expected_purpose": "LIVE",
                "requesting_owner_user_id": 7,
                "expected_live_session_id": "session-7",
            },
        ),
        (
            "release",
            {
                "channel_key": "live-monitor-channel",
                "generation": 3,
                "reason": "live_stopped",
            },
        ),
    ]
    assert signaled_process_groups == [702]
    assert streamlink_process.kill_calls == 0
    assert session.session_id not in service.sessions
    assert session.session_id not in service.user_sessions["7"]


@pytest.mark.asyncio
async def test_live_stop_revalidates_persisted_identity_before_sigterm(
    monkeypatch, tmp_path
):
    from app.services import live_streaming_service
    from app.services.live_streaming_service import (
        LiveStreamSession,
        LiveStreamingService,
        TwitchUpstreamStopForbidden,
    )
    from app.services.twitch_upstream_coordinator import ProcessIdentity

    identity_changed = False
    releases = []

    class Coordinator:
        async def assert_stop_authorized(self, **values):
            nonlocal identity_changed
            identity_changed = True

        async def inspect_process_identity(self, process_pid):
            assert process_pid == 701
            return ProcessIdentity(
                pid=701,
                process_group_id=9701,
                started_at=datetime.utcnow(),
                fingerprint="foreign-birth-701",
            )

        async def release(self, **values):
            releases.append(values)
            return True

    class Process:
        def __init__(self, pid, returncode=None):
            self.pid = pid
            self.returncode = returncode

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    streamlink_process = Process(701)
    ffmpeg_process = Process(702, returncode=0)
    session = LiveStreamSession(
        session_id="session-7",
        streamer_name="streamer",
        quality="best",
        streamlink_process=streamlink_process,
        ffmpeg_process=ffmpeg_process,
        output_dir=tmp_path,
        user_id="7",
        channel_key="live-stop-channel",
        lease_generation=3,
        process_group_id=701,
        process_start_fingerprint="birth-701",
    )
    service = LiveStreamingService(coordinator=Coordinator(), output_root=tmp_path)
    service.sessions[session.session_id] = session
    service.user_sessions = {"7": {session.session_id}}
    signaled = []

    monkeypatch.setattr(
        live_streaming_service.os,
        "getpgid",
        lambda process_pid: 9701 if identity_changed else process_pid,
    )

    def kill_process_group(process_group_id, sig):
        signaled.append((process_group_id, sig))
        streamlink_process.returncode = -sig

    monkeypatch.setattr(live_streaming_service.os, "killpg", kill_process_group)

    with pytest.raises(TwitchUpstreamStopForbidden):
        await service.stop_stream(session.session_id, requesting_user_id="7")

    assert signaled == []
    assert releases == []
    assert session.is_active is True


@pytest.mark.asyncio
async def test_live_stop_revalidates_persisted_identity_before_sigkill(
    monkeypatch, tmp_path
):
    from app.services import live_streaming_service
    from app.services.live_streaming_service import (
        LiveStreamSession,
        LiveStreamingService,
        TwitchUpstreamStopForbidden,
    )
    from app.services.twitch_upstream_coordinator import ProcessIdentity

    identity_changed = False
    releases = []

    class Coordinator:
        async def assert_stop_authorized(self, **values):
            return None

        async def inspect_process_identity(self, process_pid):
            assert process_pid == 701
            return ProcessIdentity(
                pid=701,
                process_group_id=701,
                started_at=datetime.utcnow(),
                fingerprint=("foreign-birth-701" if identity_changed else "birth-701"),
            )

        async def release(self, **values):
            releases.append(values)
            return True

    class Process:
        def __init__(self, pid, returncode=None):
            self.pid = pid
            self.returncode = returncode

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    streamlink_process = Process(701)
    ffmpeg_process = Process(702, returncode=0)
    session = LiveStreamSession(
        session_id="session-7",
        streamer_name="streamer",
        quality="best",
        streamlink_process=streamlink_process,
        ffmpeg_process=ffmpeg_process,
        output_dir=tmp_path,
        user_id="7",
        channel_key="live-stop-channel",
        lease_generation=3,
        process_group_id=701,
        process_start_fingerprint="birth-701",
    )
    service = LiveStreamingService(coordinator=Coordinator(), output_root=tmp_path)
    service.sessions[session.session_id] = session
    service.user_sessions = {"7": {session.session_id}}
    signaled = []

    monkeypatch.setattr(live_streaming_service.os, "getpgid", lambda process_pid: 701)

    def kill_process_group(process_group_id, sig):
        signaled.append((process_group_id, sig))
        if sig == live_streaming_service.signal.SIGKILL:
            streamlink_process.returncode = -sig

    async def expire_wait(awaitable, timeout):
        nonlocal identity_changed
        awaitable.close()
        identity_changed = True
        raise asyncio.TimeoutError

    monkeypatch.setattr(live_streaming_service.os, "killpg", kill_process_group)
    monkeypatch.setattr(live_streaming_service.asyncio, "wait_for", expire_wait)

    with pytest.raises(TwitchUpstreamStopForbidden):
        await service.stop_stream(session.session_id, requesting_user_id="7")

    assert signaled == [(701, live_streaming_service.signal.SIGTERM)]
    assert releases == []
    assert session.is_active is True


@pytest.mark.asyncio
async def test_live_ffmpeg_reap_revalidates_identity_before_sigkill(
    monkeypatch, tmp_path
):
    from app.services import live_streaming_service
    from app.services.live_streaming_service import LiveStreamingService
    from app.services.twitch_upstream_coordinator import ProcessIdentity

    identity_changed = False

    class Coordinator:
        async def inspect_process_identity(self, process_pid):
            assert process_pid == 702
            return ProcessIdentity(
                pid=702,
                process_group_id=702,
                started_at=datetime.utcnow(),
                fingerprint=("foreign-birth-702" if identity_changed else "birth-702"),
            )

    class Process:
        pid = 702
        returncode = None

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    process = Process()
    service = LiveStreamingService(coordinator=Coordinator(), output_root=tmp_path)
    signaled = []

    monkeypatch.setattr(live_streaming_service.os, "getpgid", lambda process_pid: 702)

    def kill_process_group(process_group_id, sig):
        signaled.append((process_group_id, sig))
        if sig == live_streaming_service.signal.SIGKILL:
            process.returncode = -sig

    async def expire_wait(awaitable, timeout):
        nonlocal identity_changed
        awaitable.close()
        identity_changed = True
        raise asyncio.TimeoutError

    monkeypatch.setattr(live_streaming_service.os, "killpg", kill_process_group)
    monkeypatch.setattr(live_streaming_service.asyncio, "wait_for", expire_wait)

    assert (
        await service._reap_process(
            process,
            process_group_id=702,
            process_start_fingerprint="birth-702",
        )
        is False
    )
    assert signaled == [(702, live_streaming_service.signal.SIGTERM)]
