"""Real application admin boundary: current policy and no forbidden effects."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from fastapi.routing import iter_route_contexts
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


from app.database import Base, DatabaseLifecycle
from app.dependencies import get_auth_service, get_db, require_admin_user
from app.main import create_app
from app.models import User
from app.services.core.api_key_service import ApiKeyService
from app.services.core.auth_service import AuthService
from app.services.background_queue_cleanup_service import BackgroundQueueCleanupService
from app.utils.token_store import ShareTokenModel


@pytest.fixture
def admin_stack(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        AUTH_JWT_SECRET="admin-policy-test-secret-at-least-thirty-two-characters",
        AUTH_JWT_ALGORITHM="HS256",
        AUTH_JWT_ISSUER="admin-policy-test",
        AUTH_JWT_AUDIENCE="admin-policy-api",
        AUTH_ACCESS_TOKEN_MINUTES=15,
    )
    lifecycle = DatabaseLifecycle("sqlite://")
    engine = lifecycle.sync_engine
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        with factory() as db:
            yield db

    def test_auth(db=Depends(get_db)):
        return AuthService(db, settings=settings)

    import app.database as database

    import app.config.settings as config
    import app.routes.admin as admin

    monkeypatch.setattr(database, "SessionLocal", factory)

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(RECORDING_DIRECTORY=str(tmp_path)),
    )
    # Only disposable local paths pass this test's filesystem boundary.
    import app.utils.security as security

    def local_path(path, _operation):
        assert Path(path).resolve().is_relative_to(tmp_path)
        return path

    monkeypatch.setattr(security, "validate_path_security", local_path)
    queue = SimpleNamespace(
        external_tasks={
            "recording_7": SimpleNamespace(
                task_type="recording",
                progress=100,
                status="running",
                started_at=None,
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        },
        active_tasks={},
    )

    async def capture_liveness(task_id):
        assert task_id == "recording_7"
        return False  # Explicitly abandoned capture, not an age-only completion.

    def complete_task(task_id, *, success):
        queue.external_tasks[task_id].status = "completed" if success else "failed"

    queue.recording_task_liveness = capture_liveness
    queue.complete_external_task = complete_task
    monkeypatch.setattr(admin, "_background_queue_service", queue)
    import app.services.background_queue_cleanup_service as cleanup

    monkeypatch.setattr(
        cleanup, "get_cleanup_service", lambda: BackgroundQueueCleanupService(queue)
    )
    with factory() as db:
        db.add(
            User(
                username="setup-admin", password="unused", is_admin=True, is_active=True
            )
        )
        db.add(
            ShareTokenModel(
                id=1,
                token="synthetic-share",
                stream_id=1,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    sentinel = tmp_path / "recording.ts"
    sentinel.write_bytes(b"synthetic recording")
    app = create_app(
        settings=settings,
        database=lifecycle,
        service_overrides={
            get_db: test_db,
            get_auth_service: test_auth,
            admin.get_application_background_queue_service: lambda: queue,
        },
    )
    # No lifespan: no provider connections, schedulers or startup cleanup.
    yield app, settings, factory, sentinel, queue
    lifecycle.dispose_sync()


@pytest.mark.parametrize(
    "case", ["eligible", "missing", "too_small", "already_mp4", "enqueue_error"]
)
def test_mounted_single_recording_recovery_contract(admin_stack, monkeypatch, case):
    """The real registered route must reach the native compatibility adapter."""
    import importlib

    from app.models import Recording, Stream, Streamer
    from app.services.recording.orphaned_recovery_service import OrphanedRecoveryService

    app, _settings, factory, media, _queue = admin_stack
    media.write_bytes(b"synthetic-media-966" * 128 if case != "too_small" else b"tiny")
    if case == "already_mp4":
        media.with_suffix(".mp4").write_bytes(b"existing-final-media")
    before = media.read_bytes()
    with factory() as db:
        streamer = Streamer(username="synthetic966", twitch_id="synthetic966")
        db.add(streamer)
        db.flush()
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        stream = Stream(
            streamer_id=streamer.id,
            title="offline",
            started_at=start,
            ended_at=start + timedelta(hours=1),
        )
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id, path=str(media), status="stopped", start_time=start
        )
        db.add(recording)
        db.commit()
        recording_id, stream_id = recording.id, stream.id

    adapter = OrphanedRecoveryService()
    enqueued = []

    async def get_adapter():
        return adapter

    async def enqueue(**payload):
        enqueued.append(payload)
        if case == "enqueue_error":
            raise RuntimeError("synthetic enqueue failure")
        return "synthetic-recovery-job"

    recovery = importlib.import_module(
        "app.services.recording.orphaned_recovery_service"
    )
    queue_init = importlib.import_module("app.services.init.background_queue_init")
    monkeypatch.setattr(recovery, "get_orphaned_recovery_service", get_adapter)
    monkeypatch.setattr(queue_init, "enqueue_recording_post_processing", enqueue)
    headers = credential_headers(admin_stack, "jwt", "admin")
    target_id = recording_id + 1000 if case == "missing" else recording_id
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/admin/orphaned/recover/{target_id}", headers=headers
        )
    finally:
        client.close()
    assert response.status_code == (404 if case == "missing" else 200)
    if case != "missing":
        assert response.json()["success"] is (case == "eligible")
    assert len(enqueued) == (1 if case in {"eligible", "enqueue_error"} else 0)
    if enqueued:
        assert enqueued[0]["recording_id"] == recording_id
        assert enqueued[0]["stream_id"] == stream_id
        assert enqueued[0]["ts_file_path"] == str(media)
    if case == "eligible":
        assert response.json()["data"]["file_size"] == len(before)
    assert media.read_bytes() == before
    with factory() as db:
        assert db.get(Recording, recording_id).status == "stopped"


@pytest.mark.parametrize("endpoint", ["statistics", "scan"])
def test_mounted_recovery_preview_is_read_only(admin_stack, monkeypatch, endpoint):
    import importlib

    from app.models import Stream, Streamer
    from app.services.recording.recording_manager import RecordingManager
    from app.services.recording.unified_recovery_service import UnifiedRecoveryService

    app, _settings, factory, sentinel, _queue = admin_stack
    headers = credential_headers(admin_stack, "jwt", "admin")
    root = sentinel.parent / "recordings"
    directory = root / "synthetic951" / "Season 2026" / "synthetic951_orphan_segments"
    directory.mkdir(parents=True)
    media = directory / "segment_001.ts"
    media.write_bytes(b"synthetic original segment")
    with factory() as db:
        streamer = Streamer(username="synthetic951", twitch_id="synthetic951")
        db.add(streamer)
        db.flush()
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        db.add(
            Stream(
                streamer_id=streamer.id,
                started_at=start,
                ended_at=start + timedelta(hours=1),
            )
        )
        db.commit()
    service = UnifiedRecoveryService()
    service.recordings_base_path = root
    manager = RecordingManager.__new__(RecordingManager)
    from app.services.recording.process_manager import ProcessManager

    processes = object.__new__(ProcessManager)
    processes.active_processes = {}
    processes.long_stream_processes = {}
    processes.lock = asyncio.Lock()
    manager._service = SimpleNamespace(
        get_active_recordings=lambda: {}, process_manager=processes
    )
    recovery = importlib.import_module(
        "app.services.recording.unified_recovery_service"
    )
    api = importlib.import_module("app.api.unified_recovery_endpoints")

    async def get_service():
        return service

    monkeypatch.setattr(recovery, "SessionLocal", factory)
    monkeypatch.setattr(recovery, "get_recording_manager", lambda: manager)
    app.dependency_overrides[api.get_application_recovery_service] = get_service

    def snapshot():
        with factory() as db:
            return {
                table.name: list(db.execute(select(table)).tuples())
                for table in Base.metadata.sorted_tables
            }

    before = snapshot()
    client = TestClient(app)
    try:
        url = f"/api/recording/recovery/{endpoint}"
        response = (
            client.get(url, headers=headers)
            if endpoint == "statistics"
            else client.post(url, json={"dry_run": True}, headers=headers)
        )
    finally:
        client.close()
    assert response.status_code == 200
    assert response.json()["statistics"]["orphaned_segments"] == 1
    assert snapshot() == before
    assert media.read_bytes() == b"synthetic original segment"


def credential_headers(stack, mode, state):
    _app, settings, factory, _sentinel, _queue = stack
    headers = {"accept": "application/json"}
    if state == "anonymous":
        return headers
    with factory() as db:
        user = User(
            username=f"{mode}-{state}",
            password="unused",
            is_active=True,
            is_admin=state != "nonadmin",
        )
        db.add(user)
        db.commit()
        service = AuthService(db, settings)
        if mode in {"jwt", "cookie"}:
            token = service.create_access_token(user)
            headers.update(
                {"Authorization": f"Bearer {token}"}
                if mode == "jwt"
                else {"Cookie": f"access_token={token}"}
            )
        elif mode.startswith("legacy"):
            token = asyncio.run(service.create_session(user.id))
            headers.update(
                {"Cookie": f"session={token}"}
                if mode == "legacy"
                else {"Authorization": f"Bearer {token}"}
            )
        else:
            _, token = ApiKeyService(db).create(user.id, "admin policy")
            headers.update(
                {"X-API-Key": token}
                if mode == "api-key"
                else {"Authorization": f"ApiKey {token}"}
            )
        if state == "disabled":
            user.is_active = False
        elif state == "demoted":
            user.is_admin = False
        db.commit()
    return headers


MODES = ["jwt", "cookie", "legacy", "legacy-bearer", "api-key", "api-key-authorization"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "state", ["anonymous", "nonadmin", "admin", "disabled", "demoted"]
)
def test_admin_current_policy_before_database_and_file_effects(
    admin_stack, mode, state
):
    app, _settings, factory, sentinel, queue = admin_stack
    headers = credential_headers(admin_stack, mode, state)
    expected = 200 if state == "admin" else 403
    if state in {"anonymous", "disabled"} or (
        state == "demoted" and mode in {"jwt", "cookie"}
    ):
        expected = 401

    def business_snapshot():
        with factory() as db:
            return {
                table.name: [
                    tuple(row)
                    for row in db.execute(
                        select(
                            *[
                                column
                                for column in table.columns
                                if not (
                                    table.name == "api_keys"
                                    and column.name == "last_used_at"
                                )
                            ]
                        )
                    )
                ]
                for table in Base.metadata.sorted_tables
            }

    before = business_snapshot()
    client = TestClient(app)
    try:
        read = client.get("/api/admin/tests/available", headers=headers)
        deleted = client.delete("/api/admin/share-tokens/1", headers=headers)
        cleanup = client.post("/api/admin/maintenance/cleanup-temp", headers=headers)
        jobs = client.post(
            "/api/admin/background-queue/cleanup/stuck-recordings", headers=headers
        )
        assert [
            read.status_code,
            deleted.status_code,
            cleanup.status_code,
            jobs.status_code,
        ] == [expected] * 4
        with factory() as db:
            assert (db.get(ShareTokenModel, 1) is None) == (state == "admin")
        assert sentinel.exists()  # #938: even an admin preview must preserve media.
        assert queue.external_tasks["recording_7"].status == (
            "failed" if state == "admin" else "running"
        )
        assert queue.active_tasks == {}
        if state != "admin":
            assert business_snapshot() == before
            assert sentinel.read_bytes() == b"synthetic recording"
    finally:
        client.close()


def test_every_mounted_admin_operation_has_current_user_guard(admin_stack):
    app, *_ = admin_stack
    operations = []
    for context in iter_route_contexts(app.routes):
        if context.path.startswith(("/api/admin/", "/admin/")):
            assert require_admin_user in [
                dependency.call for dependency in context.dependant.dependencies
            ], context.path
            operations.extend((context.path, method) for method in context.methods)
    assert ("/api/admin/share-tokens/{token_id}", "DELETE") in operations
    assert ("/api/admin/post-processing/retry-specific", "POST") in operations
    assert ("/admin/websocket-connections", "GET") in operations


@pytest.mark.parametrize("mode", MODES)
def test_nested_admin_and_monitoring_policy_before_body_validation(admin_stack, mode):
    app, *_ = admin_stack
    client = TestClient(app)
    try:
        for state, expected in [("nonadmin", 403), ("admin", 200)]:
            headers = credential_headers(admin_stack, mode, state)
            monitoring = client.get("/admin/websocket-connections", headers=headers)
            nested = client.post(
                "/api/admin/post-processing/retry-specific", headers=headers, json={}
            )
            assert monitoring.status_code == expected
            assert nested.status_code == (422 if state == "admin" else 403)
        assert (
            client.put("/api/admin/tests/available", headers=headers).status_code == 405
        )
    finally:
        client.close()


@pytest.mark.parametrize("mode", ["cookie", "legacy"])
def test_admin_cookie_mutation_retains_csrf_boundary(admin_stack, mode):
    app, *_ = admin_stack
    headers = credential_headers(admin_stack, mode, "admin")
    client = TestClient(app)
    try:
        response = client.delete(
            "/api/admin/share-tokens/1",
            headers=headers | {"origin": "https://foreign.invalid"},
        )
        assert response.status_code == 403
        assert response.json() == {"error": "CSRF validation failed"}
        assert (
            client.delete(
                "/api/admin/share-tokens/1",
                headers=headers | {"origin": "http://testserver"},
            ).status_code
            == 200
        )
    finally:
        client.close()
