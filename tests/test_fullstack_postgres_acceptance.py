"""Opt-in UX09 B1-B5 acceptance through the real ASGI/PostgreSQL seams.

Run this module with an isolated PostgreSQL database via
``STREAMVAULT_POSTGRES_TEST_URL``.  Unlike the focused route tests, this suite
uses ``create_app`` with its production middleware/dependencies and does not
replace authentication, share-token persistence, or websocket transport.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from app.database import Base
from app.models import (
    GlobalSettings,
    NotificationState,
    Recording,
    Stream,
    Streamer,
    TwitchUpstreamLease,
    User,
)
from app.services.core.auth_service import AuthService
from app.utils.token_store import ShareTokenModel


@pytest.fixture(scope="module")
def fullstack_runtime(tmp_path_factory, request):
    url = os.environ.get("STREAMVAULT_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("requires isolated STREAMVAULT_POSTGRES_TEST_URL")

    engine = create_engine(url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    runtime_dir = tmp_path_factory.mktemp("ux09-live-runtime")
    media_dir = runtime_dir / "recordings"
    for directory in (
        runtime_dir / "logs",
        runtime_dir / "logs" / "streamlink",
        runtime_dir / "logs" / "ffmpeg",
        runtime_dir / "logs" / "app",
        media_dir / ".artwork",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": str(runtime_dir),
        "DATABASE_URL": url,
        "AUTH_JWT_SECRET": "ux09-local-acceptance-secret-at-least-32-characters",
        "TWITCH_APP_ID": "ux09-synthetic-app",
        "TWITCH_APP_SECRET": "ux09-synthetic-secret",
        "BASE_URL": base_url,
        "ENVIRONMENT": "development",
        "SECURE_COOKIES": "false",
        "USE_SECURE_COOKIES": "false",
        "READINESS_REQUIRED_COMPONENTS": "database",
        "LOG_DIR": str(runtime_dir / "logs"),
        "STREAMLINK_LOG_DIR": str(runtime_dir / "logs" / "streamlink"),
        "FFMPEG_LOG_DIR": str(runtime_dir / "logs" / "ffmpeg"),
        "APP_LOG_DIR": str(runtime_dir / "logs" / "app"),
        "LOGS_BASE_DIR": str(runtime_dir / "logs"),
        "RECORDING_DIRECTORY": str(media_dir),
        "ARTWORK_BASE_PATH": str(media_dir / ".artwork"),
    }
    server_log = runtime_dir / "uvicorn.log"
    with server_log.open("wb") as log_handle:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=child_env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        client = httpx.Client(base_url=base_url, timeout=10)

        def cleanup_runtime():
            client.close()
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
            Base.metadata.drop_all(engine)
            engine.dispose()
            (media_dir / "ux09-fullstack.ts").unlink(missing_ok=True)

        request.addfinalizer(cleanup_runtime)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if server.poll() is not None:
                pytest.fail(f"live application exited during startup ({server.returncode})")
            try:
                readiness = client.get("/api/health/ready")
                if readiness.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("live application did not become database-ready")

        setup = client.post(
            "/auth/setup",
            json={"username": "acceptance-admin", "password": "acceptance-password"},
        )
        assert setup.status_code == 200, setup.text

    media_path = media_dir / "ux09-fullstack.ts"
    media_bytes = b"streamvault-synthetic-media"
    media_path.write_bytes(media_bytes)

    now = datetime.now(timezone.utc)
    with Session() as db:
        settings = db.get(GlobalSettings, 1)
        assert settings is not None
        settings.notification_url = ""
        settings.notifications_enabled = True
        settings.notify_recording_failed = True
        settings.supported_codecs = "h264,h265"
        settings.http_proxy = ""
        settings.https_proxy = ""
        auth = AuthService(db)
        db.add(
            User(
                username="acceptance-viewer",
                password=auth.hash_password("viewer-password"),
                is_admin=False,
                is_active=True,
            )
        )
        streamer = Streamer(
            twitch_id="ux09-fullstack-streamer",
            username="ux09-fullstack",
            is_test_data=True,
        )
        db.add(streamer)
        db.flush()
        stream = Stream(
            streamer_id=streamer.id,
            title="UX09 synthetic media",
            twitch_stream_id="ux09-fullstack-stream",
            started_at=now,
            recording_path=str(media_path),
        )
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id,
            start_time=now,
            status="recording",
            path=str(media_path),
        )
        db.add(recording)
        db.flush()
        db.add(
            TwitchUpstreamLease(
                channel_key="ux09-fullstack",
                recording_id=recording.id,
                purpose="RECORDING",
                state="ROTATING",
                generation=1,
                auth_key="synthetic-auth-key",
                auth_requested=True,
                anonymous_available=True,
                handoff_reason="awaiting_higher_priority_handoff",
                partial_recording_warning=True,
                reserved_at=now,
                heartbeat_at=now,
                expires_at=now + timedelta(minutes=5),
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        stream_id = stream.id
        streamer_id = streamer.id

    yield {
        "client": client,
        "Session": Session,
        "stream_id": stream_id,
        "streamer_id": streamer_id,
        "media_bytes": media_bytes,
        "websocket_url": f"ws://127.0.0.1:{port}/ws",
    }


def test_b1_real_login_csrf_and_forbidden_are_distinct(fullstack_runtime):
    client = fullstack_runtime["client"]

    anonymous = httpx.Client(base_url=client.base_url, timeout=10)
    try:
        unauthenticated = anonymous.get("/api/settings", headers={"accept": "application/json"})
        assert unauthenticated.status_code == 401

        login = anonymous.post(
            "/auth/login",
            json={"username": "acceptance-viewer", "password": "viewer-password"},
        )
        assert login.status_code == 200
        forbidden = anonymous.post("/api/settings", json={})
        assert forbidden.status_code == 403
    finally:
        anonymous.close()

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    csrf = client.post(
        "/api/settings",
        json=settings.json(),
        headers={"origin": "https://cross-site.invalid"},
    )
    assert csrf.status_code == 403
    assert csrf.json() == {"error": "CSRF validation failed"}


def test_b2_recording_state_round_trip_uses_public_application(fullstack_runtime):
    client = fullstack_runtime["client"]
    streamer_id = fullstack_runtime["streamer_id"]

    saved = client.post(
        f"/api/recording/streamers/{streamer_id}",
        json={
            "streamer_id": streamer_id,
            "enabled": True,
            "quality": "best",
            "twitch_auth_priority": -25,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["twitch_auth_priority"] == -25

    active = client.get("/api/recording/active")
    assert active.status_code == 200, active.text
    state = next(item for item in active.json() if item["streamer_id"] == streamer_id)
    assert state["effective_auth_mode"] == "authenticated"
    assert state["pending_handoff"] is True
    assert state["partial_recording_warning"] is True


def test_b3_real_websocket_delivery_replay_recovery_and_auth_loss(fullstack_runtime):
    client = fullstack_runtime["client"]
    websocket_url = fullstack_runtime["websocket_url"]

    session_token = client.cookies.get("session")
    assert session_token
    auth_headers = {"authorization": f"Bearer {session_token}"}

    with connect(websocket_url, additional_headers=auth_headers) as websocket:
        connected = json.loads(websocket.recv())
        assert connected["type"] == "connection.status"

        emitted = client.post("/api/settings/test-websocket-notification")
        assert emitted.status_code == 200, emitted.text
        live_event = json.loads(websocket.recv())
        assert live_event["type"] == "channel.update"
        assert live_event["event_id"] > 0

    replay = client.get("/api/realtime/events", params={"since": 0})
    assert replay.status_code == 200, replay.text
    replayed = next(
        event for event in replay.json()["events"] if event["event_id"] == live_event["event_id"]
    )
    assert replayed["data"]["test_id"] == live_event["data"]["test_id"]

    caught_up = client.get(
        "/api/realtime/events", params={"since": live_event["event_id"]}
    )
    assert caught_up.status_code == 200
    assert caught_up.json()["events"] == []

    with connect(websocket_url) as anonymous:
        with pytest.raises(ConnectionClosed) as closed:
            anonymous.recv()
        assert closed.value.code == 4001


def test_b4_persisted_share_expiry_and_synthetic_media_ranges(fullstack_runtime):
    client = fullstack_runtime["client"]
    Session = fullstack_runtime["Session"]
    stream_id = fullstack_runtime["stream_id"]
    media_bytes = fullstack_runtime["media_bytes"]

    created = client.post(f"/api/videos/{stream_id}/share-token")
    assert created.status_code == 200, created.text
    token = parse_qs(urlparse(created.json()["share_url"]).query)["token"][0]

    seek = client.get(
        f"/api/videos/public/{stream_id}",
        params={"token": token},
        headers={"range": "bytes=4-8"},
    )
    assert seek.status_code == 206
    assert seek.content == media_bytes[4:9]
    assert seek.headers["content-range"] == f"bytes 4-8/{len(media_bytes)}"

    unsatisfiable = client.get(
        f"/api/videos/public/{stream_id}",
        params={"token": token},
        headers={"range": f"bytes={len(media_bytes)}-"},
    )
    assert unsatisfiable.status_code == 416
    assert unsatisfiable.headers["content-range"] == f"bytes */{len(media_bytes)}"

    with Session() as db:
        stored = db.query(ShareTokenModel).filter_by(token=token).one()
        stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    expired = client.get(
        f"/api/videos/public/{stream_id}", params={"token": token}
    )
    assert expired.status_code == 401


def test_b5_settings_notifications_and_database_readiness_round_trip(fullstack_runtime):
    client = fullstack_runtime["client"]
    Session = fullstack_runtime["Session"]

    current = client.get("/api/settings")
    assert current.status_code == 200, current.text
    payload = current.json()
    payload["notifications_enabled"] = False
    payload["notify_recording_failed"] = False
    saved = client.post("/api/settings", json=payload)
    assert saved.status_code == 200, saved.text

    restored = client.get("/api/settings")
    assert restored.status_code == 200
    assert restored.json()["notifications_enabled"] is False
    assert restored.json()["notify_recording_failed"] is False

    cleared = client.post("/api/notifications/clear", json={})
    assert cleared.status_code == 200, cleared.text
    state = client.get("/api/notifications/state")
    assert state.status_code == 200
    assert state.json()["last_cleared_timestamp"] is not None
    with Session() as db:
        assert db.query(NotificationState).filter_by(user_id=1).one().last_cleared_timestamp

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["checks"]["database"] == "healthy"
    readiness = client.get("/api/health/ready")
    assert readiness.json()["checks"]["database"] == "ready"
