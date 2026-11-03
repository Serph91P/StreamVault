"""Recording settings use the existing global codec row, not a parallel setting."""

import asyncio
import importlib
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import (
    GlobalSettings,
    RecordingSettings,
    Streamer,
    StreamerRecordingSettings,
)
from app.routes import recording
from app.services.system.streamlink_config_service import streamlink_config_service
from app.services.system.twitch_token_service import TwitchTokenService


@pytest.fixture
def codec_api(monkeypatch, tmp_path):
    # File-backed DB and separate sessions ensure a response cannot fake persistence.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(recording, "SessionLocal", sessions)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    config_path = tmp_path / "config.twitch"
    anonymous_path = tmp_path / "config.twitch-anonymous"
    monkeypatch.setattr(streamlink_config_service, "config_dir", tmp_path)
    monkeypatch.setattr(streamlink_config_service, "twitch_config_path", config_path)
    monkeypatch.setattr(
        streamlink_config_service, "twitch_anonymous_config_path", anonymous_path
    )
    # No Twitch calls or real credentials: config generation itself remains real.
    monkeypatch.setattr(
        TwitchTokenService, "get_valid_access_token", AsyncMock(return_value=None)
    )
    app = FastAPI()
    app.include_router(recording.router)
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            sessions=sessions,
            config=config_path,
            anonymous_config=anonymous_path,
        )
    engine.dispose()


@pytest.mark.parametrize("use_global", [False, True])
def test_streamer_list_reads_persisted_cleanup_inheritance(codec_api, use_global):
    with codec_api.sessions() as db:
        db.add(
            Streamer(id=933, username="synthetic-channel", twitch_id="synthetic-933")
        )
        db.add(
            StreamerRecordingSettings(
                streamer_id=933, use_global_cleanup_policy=use_global
            )
        )
        db.commit()
    response = codec_api.client.get("/api/recording/streamers")
    assert response.status_code == 200, response.text
    assert response.json()[0]["use_global_cleanup_policy"] is use_global


def test_post_persists_global_codec_and_get_reads_it(codec_api):
    response = codec_api.client.post(
        "/api/recording/settings", json={"supported_codecs": "av1,h265,h264"}
    )
    assert response.status_code == 200, response.text
    with codec_api.sessions() as db:
        row = db.query(GlobalSettings).one()
        assert row.supported_codecs == "av1,h265,h264"
        assert "supported_codecs" not in RecordingSettings.__table__.columns
    assert response.json()["supported_codecs"] == "av1,h265,h264"
    assert (
        codec_api.client.get("/api/recording/settings").json()["supported_codecs"]
        == "av1,h265,h264"
    )
    assert "twitch-supported-codecs=av1,h265,h264\n" in codec_api.config.read_text()


@pytest.mark.parametrize(
    "codecs", ["vp9", "h264,unknown", "", "h264\ninjected=1", None, ["h264"]]
)
def test_invalid_codec_does_not_change_persisted_settings(codec_api, codecs):
    with codec_api.sessions() as db:
        db.add(GlobalSettings(supported_codecs="h265,h264"))
        db.add(RecordingSettings(default_quality="720p"))
        db.commit()
    response = codec_api.client.post(
        "/api/recording/settings",
        json={"supported_codecs": codecs, "default_quality": "best"},
    )
    assert response.status_code == 422, response.text
    with codec_api.sessions() as db:
        assert db.query(GlobalSettings).one().supported_codecs == "h265,h264"
        assert db.query(RecordingSettings).one().default_quality == "720p"
    assert not codec_api.config.exists()


@pytest.mark.parametrize("method", ["get", "post"])
def test_fresh_settings_use_existing_global_default(codec_api, method):
    response = codec_api.client.request(
        method, "/api/recording/settings", **({"json": {}} if method == "post" else {})
    )
    assert response.status_code == 200, response.text
    assert response.json()["supported_codecs"] == "h264,h265"
    with codec_api.sessions() as db:
        assert db.query(GlobalSettings).one().supported_codecs == "h264,h265"


def test_old_client_preserves_global_and_other_global_settings(codec_api):
    with codec_api.sessions() as db:
        db.add(
            GlobalSettings(
                supported_codecs="av1,h265,h264",
                notifications_enabled=False,
                prefer_higher_quality=False,
                twitch_max_concurrent_upstreams=3,
            )
        )
        db.commit()
    response = codec_api.client.post(
        "/api/recording/settings", json={"default_quality": "720p"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["supported_codecs"] == "av1,h265,h264"
    with codec_api.sessions() as db:
        row = db.query(GlobalSettings).one()
        assert row.supported_codecs == "av1,h265,h264"
        assert row.notifications_enabled is False
        assert row.prefer_higher_quality is False
        assert row.twitch_max_concurrent_upstreams == 3
        assert db.query(RecordingSettings).one().default_quality == "720p"
    assert not codec_api.config.exists()


@pytest.mark.parametrize("codecs", ["h264", "h264,h265", "h265,h264", "av1,h265,h264"])
def test_supported_codec_options_roundtrip_without_touching_other_fields(
    codec_api, codecs
):
    with codec_api.sessions() as db:
        db.add(GlobalSettings(notifications_enabled=False, prefer_higher_quality=False))
        db.commit()
    payload = {
        "supported_codecs": codecs,
        "enabled": False,
        "default_quality": "720p",
        "filename_template": "{streamer}/{title}",
        "filename_preset": "custom",
        "use_chapters": False,
        "use_category_as_chapter_title": True,
        "max_streams_per_streamer": 7,
        "cleanup_policy": {"type": "count", "threshold": 5},
    }
    response = codec_api.client.post("/api/recording/settings", json=payload)
    assert response.status_code == 200, response.text
    result = codec_api.client.get("/api/recording/settings").json()
    for key, value in payload.items():
        if key == "cleanup_policy":
            assert result[key]["threshold"] == 5
            assert result[key]["type"] == "count"
        else:
            assert result[key] == value
    with codec_api.sessions() as db:
        row = db.query(GlobalSettings).one()
        assert row.supported_codecs == codecs
        assert row.notifications_enabled is False
        assert row.prefer_higher_quality is False


def test_failed_commit_does_not_partially_save_codec_or_recording_settings(
    codec_api, monkeypatch
):
    with codec_api.sessions() as db:
        db.add(GlobalSettings(supported_codecs="h264"))
        db.add(RecordingSettings(default_quality="720p"))
        db.commit()

    def fail_commit(_session):
        raise RuntimeError("synthetic database failure")

    with monkeypatch.context() as patch:
        patch.setattr(codec_api.sessions.class_, "commit", fail_commit)
        response = codec_api.client.post(
            "/api/recording/settings",
            json={"supported_codecs": "av1,h265,h264", "default_quality": "best"},
        )
    assert response.status_code == 500
    with codec_api.sessions() as db:
        assert db.query(GlobalSettings).one().supported_codecs == "h264"
        assert db.query(RecordingSettings).one().default_quality == "720p"
    assert not codec_api.config.exists()


@pytest.mark.parametrize("raises", [False, True])
def test_config_failure_keeps_committed_setting_visible(codec_api, monkeypatch, raises):
    regeneration = AsyncMock(return_value=False)
    if raises:
        regeneration.side_effect = RuntimeError("synthetic config failure")
    monkeypatch.setattr(streamlink_config_service, "regenerate_config", regeneration)
    response = codec_api.client.post(
        "/api/recording/settings", json={"supported_codecs": "h264"}
    )
    assert response.status_code == 200, response.text
    regeneration.assert_awaited_once()
    with codec_api.sessions() as db:
        assert db.query(GlobalSettings).one().supported_codecs == "h264"
    assert (
        codec_api.client.get("/api/recording/settings").json()["supported_codecs"]
        == "h264"
    )


def test_unchanged_codec_does_not_regenerate_config(codec_api, monkeypatch):
    with codec_api.sessions() as db:
        db.add(GlobalSettings(supported_codecs="h264"))
        db.commit()
    regeneration = AsyncMock()
    monkeypatch.setattr(streamlink_config_service, "regenerate_config", regeneration)
    assert (
        codec_api.client.post(
            "/api/recording/settings", json={"supported_codecs": "h264"}
        ).status_code
        == 200
    )
    regeneration.assert_not_awaited()


@pytest.mark.parametrize("override", [None, "h264", "h265,h264"])
@pytest.mark.parametrize("anonymous", [False, True])
def test_recording_consumer_uses_global_unless_channel_overrides(
    codec_api, monkeypatch, tmp_path, override, anonymous
):
    """Exercise the real DB lookup and command builder; never launch Twitch."""
    with codec_api.sessions() as db:
        streamer = Streamer(username="synthetic-channel", twitch_id="933")
        db.add(streamer)
        db.flush()
        streamer_id = streamer.id
        db.add(
            StreamerRecordingSettings(
                streamer_id=streamer_id, supported_codecs=override
            )
        )
        db.add(RecordingSettings(enable_proxy=False))
        db.commit()

    response = codec_api.client.post(
        "/api/recording/settings", json={"supported_codecs": "av1,h265,h264"}
    )
    assert response.status_code == 200, response.text
    with codec_api.sessions() as db:
        assert db.query(StreamerRecordingSettings).one().supported_codecs == override
        assert db.query(GlobalSettings).one().supported_codecs == "av1,h265,h264"
    assert "twitch-supported-codecs=av1,h265,h264\n" in codec_api.config.read_text()

    module = importlib.import_module("app.services.recording.process_manager")
    manager = object.__new__(module.ProcessManager)
    manager.logging_service = None
    manager.active_processes = {}
    manager.long_stream_processes = {}
    manager.lock = asyncio.Lock()
    manager._track_segment_completion = lambda _process: None
    manager.AUTH_STARTUP_FALLBACK_WINDOW_SECONDS = 0

    class Child:
        returncode = None
        pid = 933

    child = Child()
    commands = []

    async def spawn(*command, **_kwargs):
        commands.append(command)
        return child

    async def no_delay(_seconds):
        pass

    class Notifications:
        async def send_recording_notification(self, **_kwargs):
            pass

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(module.asyncio, "sleep", no_delay)
    monkeypatch.setattr(
        "app.services.notifications.external_notification_service.ExternalNotificationService",
        Notifications,
    )
    stream = SimpleNamespace(
        id=933,
        streamer_id=streamer_id,
        streamer=SimpleNamespace(username="synthetic-channel", twitch_id="933"),
        title="Synthetic recording",
        category_name="Synthetic category",
    )
    asyncio.run(
        manager._start_segment(
            stream,
            str(tmp_path / "segment.ts"),
            "best",
            {"segment_count": 1, "total_segments": []},
            token_resolution=SimpleNamespace(
                token=None if anonymous else "synthetic",
                source=None,
                stored_version=None,
            ),
        )
    )
    effective = "h264" if anonymous else (override or "av1,h265,h264")
    assert len(commands) == 1
    assert [
        arg for arg in commands[0] if arg.startswith("--twitch-supported-codecs=")
    ] == [f"--twitch-supported-codecs={effective}"]


def test_real_http_save_and_reload(codec_api):
    """Real loopback HTTP, not a fulfilled response or mocked router."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        server = uvicorn.Server(
            uvicorn.Config(
                codec_api.client.app,
                lifespan="off",
                log_level="warning",
            )
        )
        thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [listener]},
            daemon=True,
        )
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while (
                not server.started and thread.is_alive() and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            assert server.started, "Loopback server did not start"
            with httpx.Client(
                base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
                trust_env=False,
            ) as client:
                saved = client.post(
                    "/api/recording/settings", json={"supported_codecs": "h265,h264"}
                )
                assert saved.status_code == 200, saved.text
                # Independent connection/session models a client reload.
            with httpx.Client(
                base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
                trust_env=False,
            ) as client:
                reloaded = client.get("/api/recording/settings")
                assert reloaded.status_code == 200, reloaded.text
            with codec_api.sessions() as db:
                persisted = db.query(GlobalSettings).one().supported_codecs
            assert saved.json()["supported_codecs"] == persisted == "h265,h264"
            assert reloaded.json()["supported_codecs"] == persisted
            assert (
                f"twitch-supported-codecs={persisted}\n" in codec_api.config.read_text()
            )
            print(
                {
                    "POST": saved.status_code,
                    "GET_after_new_connection": reloaded.status_code,
                    "POST_codec": saved.json()["supported_codecs"],
                    "SQLite_readback": persisted,
                    "GET_codec": reloaded.json()["supported_codecs"],
                    "generated_config_codec": persisted,
                }
            )
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive(), "Loopback server did not stop"
