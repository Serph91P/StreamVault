"""Persisted recording policy must reach the actual Streamlink child boundary."""

import asyncio
import importlib
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.dependencies import get_db, get_application_session_factory
from app.config.settings import Settings
from app.services.core.state_persistence_service import StatePersistenceService
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator
from app.models import RecordingSettings, Stream, Streamer, StreamerRecordingSettings
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_database_service import RecordingDatabaseService
from app.services.recording.recording_lifecycle_manager import RecordingLifecycleManager
from app.services.recording.recording_state_manager import RecordingStateManager


@pytest.fixture
async def recording_policy(tmp_path, monkeypatch):
    routes = importlib.import_module("app.routes.recording")
    config_module = importlib.import_module("app.services.recording.config_manager")
    process_module = importlib.import_module("app.services.recording.process_manager")
    lifecycle_module = importlib.import_module(
        "app.services.recording.recording_lifecycle_manager"
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'quality.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(routes, "SessionLocal", sessions)
    monkeypatch.setattr(config_module, "SessionLocal", sessions)
    monkeypatch.setattr("app.database.SessionLocal", sessions)
    with sessions() as db:
        db.add(Streamer(id=1, twitch_id="quality-fixture", username="quality_fixture"))
        db.add(Stream(id=1, streamer_id=1, title="Quality fixture"))
        db.add(RecordingSettings(enable_proxy=False))
        db.commit()

    def get_test_db():
        with sessions() as db:
            yield db

    app = FastAPI()
    runtime_settings = Settings(
        ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
    )
    app.state.settings = runtime_settings
    app.include_router(routes.router)
    app.include_router(importlib.import_module("app.routes.streamers").router)
    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_application_session_factory] = lambda: sessions
    config = ConfigManager(session_factory=sessions, settings=runtime_settings)
    state = RecordingStateManager.for_application(
        config, StatePersistenceService(session_factory=sessions)
    )
    process = ProcessManager.for_application(
        config_manager=config,
        post_processing_callback=AsyncMock(),
        upstream_coordinator=TwitchUpstreamCoordinator(
            sessions, monotonic_clock=monotonic
        ),
    )
    monkeypatch.setattr(
        process.upstream_coordinator, "reserve", AsyncMock(return_value=None)
    )

    process.logging_service = None
    monkeypatch.setattr(
        process, "_resolve_recording_token", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(process, "_track_recording_process", Mock())
    monkeypatch.setattr(process, "_track_segment_completion", Mock())
    monkeypatch.setattr(process, "_monitor_long_stream", AsyncMock())
    monkeypatch.setattr(
        process_module,
        "ASYNC_DELAYS",
        SimpleNamespace(PROCESS_START_GRACE=0, RECORDING_ERROR_RECOVERY=1),
    )
    monkeypatch.setattr(lifecycle_module, "background_queue_service", None)
    monkeypatch.setattr(
        "app.services.notifications.external_notification_service.ExternalNotificationService",
        lambda **_context: SimpleNamespace(send_recording_notification=AsyncMock()),
    )
    commands = []

    async def spawn(*args, **kwargs):
        commands.append(args)
        child = Mock(pid=12345, returncode=None, wait=AsyncMock(return_value=0))
        child.terminate.side_effect = lambda: setattr(child, "returncode", 0)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    lifecycle = RecordingLifecycleManager(
        config_manager=config,
        database_service=RecordingDatabaseService(session_factory=sessions),
        state_manager=state,
        process_manager=process,
        recording_logger=Mock(),
    )
    monkeypatch.setattr(
        lifecycle,
        "_generate_recording_path",
        AsyncMock(return_value=str(tmp_path / "recording.ts")),
    )
    monkeypatch.setattr(lifecycle, "monitor_and_process_recording", AsyncMock())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield SimpleNamespace(
            client=client,
            sessions=sessions,
            lifecycle=lifecycle,
            state=state,
            process=process,
            commands=commands,
            config=config,
            tmp_path=tmp_path,
        )
    for task in state.recording_tasks.values():
        task.cancel()
    await asyncio.gather(*state.recording_tasks.values(), return_exceptions=True)
    if hasattr(process, "_task_supervisor"):
        await process._task_supervisor.shutdown()
    assert process.proxy_health_service is not None
    await process.proxy_health_service.stop()
    engine.dispose()


@pytest.mark.asyncio
async def test_actual_recording_start_selects_its_notification_catalog(
    recording_policy, monkeypatch
):
    env = recording_policy
    owners = []

    def notifier(*, session_factory=None, settings=None):
        owners.append((session_factory, settings))
        return SimpleNamespace(send_recording_notification=AsyncMock())

    monkeypatch.setattr(
        "app.services.notifications.external_notification_service.ExternalNotificationService",
        notifier,
    )
    assert await env.lifecycle.start_recording(1, 1) is not None
    assert owners == [(env.sessions, env.config._settings)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("global_quality", "channel_quality", "kwargs", "expected"),
    [
        ("best", None, {}, "best"),
        ("480p", None, {}, "480p"),
        ("480p", None, {"quality": None}, "480p"),
        ("480p", "720p", {}, "720p"),
        ("480p", "best", {}, "best"),
        ("480p", None, {"quality": "360p"}, "360p"),
        ("2160p,best", None, {}, "2160p,best"),
        ("unavailable", None, {}, "unavailable"),
    ],
)
async def test_api_policy_reaches_streamlink_child(
    recording_policy, global_quality, channel_quality, kwargs, expected
):
    env = recording_policy
    response = await env.client.post(
        "/api/recording/settings", json={"default_quality": global_quality}
    )
    assert response.status_code == 200, response.text
    response = await env.client.post(
        "/api/recording/streamers/1",
        json={"streamer_id": 1, "quality": channel_quality},
    )
    assert response.status_code == 200, response.text
    with env.sessions() as db:
        assert db.query(RecordingSettings).one().default_quality == global_quality
        assert db.query(StreamerRecordingSettings).one().quality == channel_quality
    assert (await env.client.get("/api/recording/settings")).json()[
        "default_quality"
    ] == global_quality

    recording_id = await env.lifecycle.start_recording(1, 999, **kwargs)
    assert recording_id is not None
    assert len(env.commands) == 1
    command = env.commands[0]
    assert command[command.index("twitch.tv/quality_fixture") + 1] == expected
    assert "--twitch-supported-codecs=h264" in command
    assert not any(arg.startswith("--twitch-api-header") for arg in command)
    assert env.state.get_active_recording(recording_id)["quality"] == expected
    assert (
        env.lifecycle.recording_logger.log_recording_start.call_args.kwargs["quality"]
        == expected
    )

    # Real installed Streamlink resolves a deterministic offline variant catalogue.
    # Only the provider/config/output boundary is substituted; no Twitch request/media.
    plugin_dir = env.tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "qualityfixture.py").write_text(
        "import re\n"
        "from streamlink.plugin import Plugin, pluginmatcher\n"
        "from streamlink.stream.http import HTTPStream\n"
        "@pluginmatcher(re.compile(r'https://quality.invalid/'))\n"
        "class QualityFixture(Plugin):\n"
        "    def _get_streams(self):\n"
        "        return {q: HTTPStream(self.session, 'http://127.0.0.1/' + q)\n"
        "                for q in ('360p', '480p', '720p')}\n"
        "__plugin__ = QualityFixture\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlink",
            "--no-config",
            "--plugin-dirs",
            str(plugin_dir),
            "--stream-url",
            "https://quality.invalid/",
            command[command.index("twitch.tv/quality_fixture") + 1],
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    selected = {"best": "720p", "2160p,best": "720p"}.get(expected, expected)
    if expected == "unavailable":
        assert result.returncode != 0
        assert "specified stream" in (result.stdout + result.stderr).lower()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == f"http://127.0.0.1/{selected}"


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["recording", "channel-nested", "channel-flat"])
async def test_saved_policy_replaces_warm_cache_and_null_restores_inheritance(
    recording_policy, endpoint
):
    env = recording_policy

    async def channel_settings(payload):
        if endpoint == "recording":
            return await env.client.post(
                "/api/recording/streamers/1", json={"streamer_id": 1, **payload}
            )
        return await env.client.put(
            "/api/streamers/streamer/1/settings",
            json={"recording": payload} if endpoint == "channel-nested" else payload,
        )

    assert (await channel_settings({"quality": "720p"})).status_code == 200
    assert env.config.get_quality_setting(1) == "720p"
    assert (
        await env.client.post(
            "/api/recording/settings", json={"default_quality": "480p"}
        )
    ).status_code == 200
    # Omitting quality must preserve the override, explicit null must clear it.
    assert (await channel_settings({"enabled": True})).status_code == 200
    with env.sessions() as db:
        assert db.query(StreamerRecordingSettings).one().quality == "720p"
    assert (await channel_settings({"quality": None})).status_code == 200
    with env.sessions() as db:
        assert db.query(StreamerRecordingSettings).one().quality is None
    recording_id = await env.lifecycle.start_recording(1, 1, quality=None)
    assert recording_id is not None
    command = env.commands[-1]
    assert command[command.index("twitch.tv/quality_fixture") + 1] == "480p"


@pytest.mark.asyncio
async def test_resume_and_rotation_keep_resolved_quality(recording_policy):
    env = recording_policy
    assert (
        await env.client.post(
            "/api/recording/settings", json={"default_quality": "480p"}
        )
    ).status_code == 200
    resume_dir = env.tmp_path / "recording_segments"
    resume_dir.mkdir()
    (resume_dir / "recording_part001.ts").write_bytes(b"synthetic segment marker")
    recording_id = await env.lifecycle.start_recording(
        1, 1, quality=None, resume_segments_dir=str(resume_dir), recovery_generation=7
    )
    assert recording_id is not None
    assert env.commands[-1][6].endswith("recording_part002.ts")
    assert (
        env.process.upstream_coordinator.reserve.call_args.kwargs["expected_generation"]
        == 7
    )
    # Use the exact quality captured by the production rotation-monitor caller.
    stream, segment_info, quality = env.process._monitor_long_stream.call_args.args
    assert quality == "480p"
    assert await env.process._rotate_segment(stream, segment_info, quality)
    assert env.commands[-1][6].endswith("recording_part003.ts")
    assert [cmd[4] for cmd in env.commands] == ["480p", "480p"]
