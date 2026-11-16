"""#1025: mounted application, real credentials and isolated effect snapshots."""

import asyncio
from types import SimpleNamespace

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from fastapi.routing import iter_route_contexts
from sqlalchemy import select

from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.models import (
    GlobalSettings,
    RecordingSettings,
    Streamer,
    StreamerRecordingSettings,
    User,
)
from app.services.core.auth_service import AuthService
from app.services.core.api_key_service import ApiKeyService

MODES = ("jwt", "jwt-cookie", "legacy", "legacy-cookie", "key", "key-authorization")
RECORDING_WRITES = [
    ("POST", "/api/recording/settings", {"enabled": False}),
    ("POST", "/api/recording/streamers/1", {"streamer_id": 1, "enabled": False}),
    ("PUT", "/api/streamers/streamer/1/settings", {"recording": {"enabled": False}}),
    ("POST", "/api/recording/stop/1", {}),
    ("POST", "/api/recording/force-start/1", {}),
    ("POST", "/api/recording/cleanup/1", {}),
    ("POST", "/api/recording/cleanup/1/custom", {"type": "age", "threshold": 1}),
    (
        "POST",
        "/api/recording/streamers/1/cleanup-policy",
        {"type": "age", "threshold": 1},
    ),
    ("POST", "/api/recording/recovery/scan", {"dry_run": False}),
]
EXTRA_RECORDING_WRITES = [
    ("DELETE", "/api/streams/1", None),
    ("POST", "/api/recordings/force-stop", {"streamer_id": 1}),
    ("POST", "/api/streamers/synthetic-new", {}),
    ("DELETE", "/api/streamers/1", None),
    ("DELETE", "/api/streamers/1/streams/1", None),
    ("DELETE", "/api/streamers/1/streams", None),
]
ADMIN_OPERATIONS = [
    ("POST", "/api/proxy/add", {"proxy_url": "http://synthetic.invalid:8080"}),
    ("DELETE", "/api/proxy/1", None),
    ("POST", "/api/proxy/1/toggle", {}),
    ("POST", "/api/proxy/1/test", {}),
    ("POST", "/api/proxy/1/update-priority", {"priority": 3}),
    (
        "POST",
        "/api/proxy/config/update",
        {
            "enable_proxy": False,
            "proxy_health_check_enabled": False,
            "proxy_health_check_interval_seconds": 600,
            "proxy_max_consecutive_failures": 3,
            "fallback_to_direct_connection": True,
        },
    ),
    ("DELETE", "/api/streamers/subscriptions", None),
    ("POST", "/api/streamers/resubscribe-all", {}),
    ("DELETE", "/api/streamers/subscriptions/synthetic", None),
    ("GET", "/api/settings", None),
    ("POST", "/api/settings", {"notifications_enabled": False}),
    ("POST", "/api/settings/streamer/1", {"notify_online": False}),
    ("POST", "/api/settings/test-notification", {}),
    ("POST", "/api/settings/test-websocket-notification", {}),
    (
        "POST",
        "/api/background-queue/tasks/enqueue",
        {"task_type": "cleanup", "payload": {}},
    ),
    ("POST", "/api/background-queue/tasks/metadata-generation", {}),
    ("POST", "/api/background-queue/tasks/thumbnail-generation", {}),
    ("POST", "/api/background-queue/tasks/file-cleanup", {}),
    ("GET", "/api/twitch/auth-url", None),
    ("POST", "/api/twitch/manual-token", {"token": "synthetic-token"}),
    ("POST", "/api/twitch/disconnect", {}),
    ("POST", "/api/twitch/import-streamers", {}),
]
SECRETS = {
    "notification_url": "json://synthetic.invalid/NOTIFICATION_MARKER",
    "http_proxy": "http://user:HTTP_MARKER@synthetic.invalid:8080",
    "https_proxy": "https://user:HTTPS_MARKER@synthetic.invalid:8080",
}


@pytest.fixture
def stack(tmp_path, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("network is forbidden in capability tests")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    settings = SimpleNamespace(
        AUTH_JWT_SECRET="synthetic-capability-key-at-least-thirty-two-characters",
        AUTH_JWT_ALGORITHM="HS256",
        AUTH_JWT_ISSUER="capability-test",
        AUTH_JWT_AUDIENCE="capability-api",
        AUTH_ACCESS_TOKEN_MINUTES=15,
        BASE_DIR=str(tmp_path),
        RECORDING_DIRECTORY=str(tmp_path / "recordings"),
        LOG_DIR=str(tmp_path / "logs"),
        LOGS_BASE_DIR=str(tmp_path / "logs"),
        LOG_FORMAT="text",
        TWITCH_OAUTH_TOKEN=None,
        TWITCH_APP_ID="synthetic",
        TWITCH_APP_SECRET="synthetic",
        BASE_URL="http://testserver",
        ENVIRONMENT="test",
        ARTWORK_BASE_PATH=str(tmp_path / "artwork"),
    )
    database = DatabaseLifecycle("sqlite://")
    Base.metadata.create_all(database.sync_engine)
    with database.sync_session_factory() as db:
        db.add_all(
            [
                User(
                    username="setup", password="unused", is_active=True, is_admin=True
                ),
                GlobalSettings(
                    id=1,
                    proxy_encryption_key=Fernet.generate_key().decode(),
                    twitch_access_token="synthetic-old-token",
                    twitch_refresh_token="synthetic-old-refresh",
                    **SECRETS,
                ),
                RecordingSettings(id=1, enabled=True),
                Streamer(id=1, username="synthetic", twitch_id="1"),
                StreamerRecordingSettings(streamer_id=1, enabled=True),
            ]
        )
        db.commit()
    app = create_app(settings=settings, database=database)
    sentinel = tmp_path / "media.ts"
    sentinel.write_bytes(b"synthetic media must survive")
    client = TestClient(app)
    yield app, database, settings, client, tmp_path
    client.close()
    database.dispose_sync()


def headers(stack, mode, state):
    _, database, settings, _, _ = stack
    result = {"accept": "application/json", "origin": "http://testserver"}
    if state == "anonymous":
        return result
    with database.sync_session_factory() as db:
        user = User(
            username=f"{mode}-{state}",
            password="unused",
            is_active=True,
            is_admin=state != "reader",
        )
        db.add(user)
        db.commit()
        auth = AuthService(db, settings)
        if mode.startswith("jwt"):
            token = auth.create_access_token(user)
            if state in {"writer", "limited"}:
                claims = auth.decode_access_token(token)
                claims["scp"] = ["recording:read"] + (
                    ["recording:write"] if state == "writer" else []
                )
                token = jwt.encode(claims, settings.AUTH_JWT_SECRET, algorithm="HS256")
            result.update(
                {"Cookie": f"access_token={token}"}
                if mode.endswith("cookie")
                else {"Authorization": f"Bearer {token}"}
            )
        elif mode.startswith("legacy"):
            token = asyncio.run(auth.create_session(user.id))
            result.update(
                {"Cookie": f"session={token}"}
                if mode.endswith("cookie")
                else {"Authorization": f"Bearer {token}"}
            )
            if state == "revoked":
                asyncio.run(auth.delete_session(token))
        else:
            record, token = ApiKeyService(db).create(user.id, "synthetic")
            result.update(
                {"X-API-Key": token}
                if mode == "key"
                else {"Authorization": f"ApiKey {token}"}
            )
            if state == "revoked":
                ApiKeyService(db).revoke(record.id)
        if state == "disabled":
            user.is_active = False
        if state == "downgraded":
            user.is_admin = False
        if state == "revoked" and mode.startswith("jwt"):
            # JWT validity is bound to the current owner (no invented JTI store).
            user.is_active = False
        db.commit()
    return result


def snapshot(stack):
    app, database, _, _, root = stack
    with database.sync_session_factory() as db:
        rows = {
            t.name: [
                tuple(row)
                for row in db.execute(
                    select(
                        *[
                            c
                            for c in t.columns
                            if not (t.name == "api_keys" and c.name == "last_used_at")
                        ]
                    )
                )
            ]
            for t in Base.metadata.sorted_tables
        }
    files = {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    queue = app.state.background_queue_service
    return (
        rows,
        files,
        (
            dict(queue.active_tasks),
            dict(queue.external_tasks),
            queue.task_queue.qsize(),
        ),
    )


@pytest.mark.parametrize(
    "operation", RECORDING_WRITES + EXTRA_RECORDING_WRITES + ADMIN_OPERATIONS
)
def test_each_reader_boundary_before_effect(stack, operation):
    credential = headers(stack, "jwt", "reader")
    before = snapshot(stack)
    method, path, body = operation
    response = stack[3].request(method, path, headers=credential, json=body)
    assert response.status_code == 403, (path, response.status_code, response.text)
    assert snapshot(stack) == before


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "state", ["reader", "downgraded", "disabled", "revoked", "anonymous"]
)
def test_denied_operations_have_no_effect(stack, mode, state):
    _, _, _, client, _ = stack
    credential = headers(stack, mode, state)
    before = snapshot(stack)
    expected = (
        401
        if state in {"anonymous", "disabled", "revoked"}
        or (state == "downgraded" and mode.startswith("jwt"))
        else 403
    )
    for method, path, body in (
        RECORDING_WRITES + EXTRA_RECORDING_WRITES + ADMIN_OPERATIONS
    ):
        response = client.request(method, path, headers=credential, json=body)
        assert response.status_code == expected, (
            method,
            path,
            response.status_code,
            response.text,
        )
        assert not any(
            marker in response.text
            for marker in ("NOTIFICATION_MARKER", "HTTP_MARKER", "HTTPS_MARKER")
        )
        assert snapshot(stack) == before, (method, path)


@pytest.mark.parametrize("mode", ["jwt", "jwt-cookie"])
@pytest.mark.parametrize("state", ["limited", "writer"])
def test_scoped_admin_is_not_implicitly_unrestricted(stack, mode, state):
    _, _, _, client, _ = stack
    credential = headers(stack, mode, state)
    if state == "limited":
        for method, path, body in RECORDING_WRITES:
            assert (
                client.request(method, path, headers=credential, json=body).status_code
                == 403
            )
    for method, path, body in ADMIN_OPERATIONS:
        response = client.request(method, path, headers=credential, json=body)
        assert response.status_code == 403, (path, response.text)


@pytest.mark.parametrize("mode", MODES + ("writer-jwt", "writer-jwt-cookie"))
def test_authorized_saves_really_persist(stack, mode):
    _, database, _, client, _ = stack
    credential = headers(
        stack,
        mode.removeprefix("writer-"),
        "writer" if mode.startswith("writer-") else "admin",
    )
    for method, path, body in RECORDING_WRITES[:3]:
        response = client.request(method, path, headers=credential, json=body)
        assert response.status_code == 200, (path, response.text)
    with database.sync_session_factory() as db:
        assert db.query(RecordingSettings).one().enabled is False
        assert db.query(StreamerRecordingSettings).one().enabled is False


@pytest.mark.parametrize("mode", MODES)
def test_admin_secret_read_save_and_omission_roundtrip(stack, mode):
    _, database, _, client, _ = stack
    credential = headers(stack, mode, "admin")
    read = client.get("/api/settings", headers=credential)
    assert read.status_code == 200
    for key, value in SECRETS.items():
        assert read.json()[key] == value
    saved = client.post(
        "/api/settings", headers=credential, json={"notify_recording_failed": False}
    )
    assert saved.status_code == 200, saved.text
    reread = client.get("/api/settings", headers=credential).json()
    assert reread["notify_recording_failed"] is False
    for key, value in SECRETS.items():
        assert reread[key] == value
    with database.sync_session_factory() as db:
        assert db.get(GlobalSettings, 1).notification_url == SECRETS["notification_url"]


def test_all_recording_mutations_are_guarded_on_the_registered_app(stack):
    from app.dependencies import require_scopes, require_admin_user

    app, *_ = stack
    operations = {
        (c.path, m): c
        for c in iter_route_contexts(app.routes)
        for m in (c.methods or ())
        if m in {"POST", "PUT", "DELETE", "PATCH"}
    }
    recording = {key for key in operations if key[0].startswith("/api/recording/")}
    expected = {
        (p.replace("/1", "/{streamer_id}"), m)
        for m, p, _ in RECORDING_WRITES
        if p.startswith("/api/recording/")
    }
    assert recording == expected
    write_modules = {
        "app.routes.recording",
        "app.routes.recordings",
        "app.routes.streamers",
        "app.routes.streams",
        "app.api.unified_recovery_endpoints",
    }
    admin_modules = {
        "app.routes.settings",
        "app.routes.background_queue",
        "app.routes.twitch_auth",
        "app.routes.proxy",
    }
    admin_endpoints = {
        "delete_all_subscriptions",
        "resubscribe_all",
        "delete_subscription",
    }
    for key, context in operations.items():
        endpoint = context.dependant.call
        if endpoint.__module__ not in write_modules | admin_modules:
            continue
        guards = [d.call for d in context.dependant.dependencies]
        if endpoint.__module__ in admin_modules or endpoint.__name__ in admin_endpoints:
            assert require_admin_user in guards, key
        else:
            assert any(
                getattr(guard, "__code__", None)
                is require_scopes("recording:write").__code__
                and any(
                    cell.cell_contents == ("recording:write",)
                    for cell in guard.__closure__
                )
                for guard in guards
            ), key


@pytest.mark.parametrize("mode", MODES + ("writer-jwt",))
@pytest.mark.parametrize("custom", [False, True])
def test_authorized_policy_and_cleanup_delete_only_owned_old_media(stack, mode, custom):
    from datetime import datetime, timedelta, timezone
    import json
    from app.models import Stream

    _, database, settings, client, root = stack
    credential = headers(
        stack,
        mode.removeprefix("writer-"),
        "writer" if mode.startswith("writer-") else "admin",
    )
    directory = root / "recordings" / "synthetic" / "Season 2026"
    directory.mkdir(parents=True)
    old, recent = directory / "old.mp4", directory / "recent.mp4"
    old.write_bytes(b"synthetic old media")
    recent.write_bytes(b"synthetic recent media")
    now = datetime.now(timezone.utc)
    with database.sync_session_factory() as db:
        for identifier, path, days in [(1, old, 10), (2, recent, 1)]:
            start = now - timedelta(days=days)
            db.add(
                Stream(
                    id=identifier,
                    streamer_id=1,
                    started_at=start,
                    ended_at=start + timedelta(hours=1),
                    recording_path=str(path),
                )
            )
        db.commit()
    policy = {
        "type": "age",
        "threshold": 7,
        "preserve_favorites": False,
        "preserve_categories": [],
    }
    saved = client.post(
        "/api/recording/streamers/1/cleanup-policy",
        headers=credential,
        json={"use_global_cleanup_policy": False, "cleanup_policy": policy},
    )
    assert saved.status_code == 200, saved.text
    with database.sync_session_factory() as db:
        assert (
            json.loads(db.query(StreamerRecordingSettings).one().cleanup_policy)[
                "threshold"
            ]
            == 7
        )
    response = client.post(
        "/api/recording/cleanup/1" + ("/custom" if custom else ""),
        headers=credential,
        json=policy if custom else None,
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted_count"] == 1
    assert not old.exists()
    assert recent.read_bytes() == b"synthetic recent media"
    assert (root / "media.ts").read_bytes() == b"synthetic media must survive"
    with database.sync_session_factory() as db:
        assert db.get(Stream, 1) is None
        assert db.get(Stream, 2) is not None


@pytest.mark.parametrize("mode", MODES)
def test_admin_queue_admission_and_disconnect_have_real_effects(stack, mode):
    app, database, _, client, _ = stack
    credential = headers(stack, mode, "admin")
    with database.sync_session_factory() as db:
        row = db.get(GlobalSettings, 1)
        row.twitch_access_token = "synthetic-stored-access"
        row.twitch_refresh_token = "synthetic-stored-refresh"
        db.commit()
    response = client.post("/api/twitch/disconnect", headers=credential)
    assert response.status_code == 200 and response.json()["success"] is True
    with database.sync_session_factory() as db:
        row = db.get(GlobalSettings, 1)
        assert row.twitch_access_token is None and row.twitch_refresh_token is None
    queued = client.post(
        "/api/background-queue/tasks/enqueue?task_type=metadata_generation",
        headers=credential,
        json={"streamer_name": "synthetic", "stream_id": 1, "output_dir": "synthetic"},
    )
    assert queued.status_code == 200, queued.text
    queue = app.state.background_queue_service
    task = queue.queue_manager.get_task(queued.json()["task_id"])
    assert task is not None and task.task_type == "metadata_generation"
    assert task.payload["stream_id"] == 1
    # Admission, not the adapter/worker outcome owned by #1033.


@pytest.mark.parametrize("mode", MODES)
def test_admin_full_secret_roundtrip_and_explicit_clear(stack, mode):
    _, database, _, client, _ = stack
    credential = headers(stack, mode, "admin")
    body = client.get("/api/settings", headers=credential).json()
    saved = client.post("/api/settings", headers=credential, json=body)
    assert saved.status_code == 200, saved.text
    for key, value in SECRETS.items():
        assert client.get("/api/settings", headers=credential).json()[key] == value
    cleared = client.post(
        "/api/settings", headers=credential, json=dict.fromkeys(SECRETS, "")
    )
    assert cleared.status_code == 200, cleared.text
    with database.sync_session_factory() as db:
        row = db.get(GlobalSettings, 1)
        assert all(getattr(row, key) == "" for key in SECRETS)


@pytest.mark.parametrize("mode", ["jwt-cookie", "legacy-cookie"])
def test_recording_cookie_csrf_remains_before_effect(stack, mode):
    credential = headers(stack, mode, "admin") | {"origin": "https://foreign.invalid"}
    before = snapshot(stack)
    response = stack[3].post(
        "/api/recording/settings", headers=credential, json={"enabled": False}
    )
    assert response.status_code == 403
    assert snapshot(stack) == before


@pytest.mark.parametrize("mode", MODES)
def test_reader_projections_remain_usable_without_credentials(stack, mode):
    credential = headers(stack, mode, "reader")
    for path in (
        "/api/recording/settings",
        "/api/recording/active",
        "/api/recording/filename-presets",
        "/api/settings/streamers",
        "/api/twitch/connection-status",
        "/api/proxy/list",
        "/api/proxy/config",
    ):
        response = stack[3].get(path, headers=credential)
        assert response.status_code == 200, (path, response.text)
        assert not any(
            marker in response.text
            for marker in (
                "NOTIFICATION_MARKER",
                "HTTP_MARKER",
                "HTTPS_MARKER",
                "synthetic-old-token",
            )
        )


@pytest.mark.parametrize("mode", MODES)
def test_admin_manual_connection_is_encrypted_and_proxy_config_persists(
    stack, mode, monkeypatch
):
    from app.services.system.twitch_token_service import TwitchTokenService
    from app.utils.proxy_encryption import get_proxy_encryption

    async def synthetic_validation(self, token):
        assert token == "synthetic-new-token"
        return {"expires_in": 7200, "user_id": "synthetic-user"}

    monkeypatch.setattr(TwitchTokenService, "_validate_token", synthetic_validation)
    _, database, _, client, _ = stack
    credential = headers(stack, mode, "admin")
    response = client.post(
        "/api/twitch/manual-token",
        headers=credential,
        json={"token": "synthetic-new-token"},
    )
    assert response.status_code == 200, response.text
    with database.sync_session_factory() as db:
        row = db.get(GlobalSettings, 1)
        assert row.twitch_access_token != "synthetic-new-token"
        assert (
            get_proxy_encryption(db).decrypt(row.twitch_access_token)
            == "synthetic-new-token"
        )
        assert row.twitch_refresh_token is None
    response = client.post(
        "/api/proxy/config/update?enable_proxy=false", headers=credential
    )
    assert response.status_code == 200, response.text
    with database.sync_session_factory() as db:
        assert db.query(RecordingSettings).one().enable_proxy is False
    url = client.get("/api/twitch/auth-url", headers=credential)
    assert url.status_code == 200, url.text
    assert "id.twitch.tv/oauth2/authorize" in url.text
