"""Signed callback retry contracts with isolated persistence and owned children.

Most cases control the recorder boundary. The real-manager cases exercise the
app-bound RecordingManager/Service/Lifecycle and native ProcessManager termination;
only external media startup is replaced by an actual owned local Python child.
No live provider or Streamlink/FFmpeg capture success is claimed by these tests.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

from aiohttp import web
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.lifespan import _close_application_images, _close_application_twitch
from app.main import create_app
from app.models import (
    Category,
    GlobalSettings,
    Recording,
    RecordingSettings,
    Stream,
    Streamer,
    StreamerRecordingSettings,
    StreamEvent,
)
from app.services.api.twitch_api import TwitchAPIService

KINDS = ("stream.online", "stream.offline", "channel.update")
FAULTS = [(kind, stage) for stage in ("session-open", "first-commit") for kind in KINDS]
FAULTS += [
    ("stream.online", "start"),
    ("stream.offline", "stop"),
    ("channel.update", "category-commit"),
]
OBSERVATIONS = []


@pytest.fixture(scope="session", autouse=True)
def export_observations():
    yield
    target = os.environ.get("SV1029_RESULTS")
    if target:
        Path(target).write_text(
            json.dumps(OBSERVATIONS, indent=2, sort_keys=True) + "\n"
        )


class ControlledRecorder:
    """Faultable admission boundary with observable child and catalog effects."""

    def __init__(self, database):
        self.database = database
        self.children = []
        self.active = {}
        self.fail_start = self.fail_stop = False
        self.starts = self.stops = self.start_attempts = self.stop_attempts = 0

    def launch(self, recording_id):
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; print('ready', flush=True); sys.stdin.buffer.read(1)",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.children.append(process)
        assert process.stdout.readline() == b"ready\n"
        self.active[recording_id] = process

    async def start_recording(self, stream_id, streamer_id, *, force_mode):
        self.start_attempts += 1
        assert streamer_id == 1 and force_mode is False
        assert self.database.sync_engine.pool.checkedout() == 0
        if self.fail_start:
            raise RuntimeError("synthetic recording admission failure")
        with self.database.sync_session_factory() as session:
            assert session.get(Stream, stream_id).ended_at is None
            assert session.query(Recording).filter_by(stream_id=stream_id).count() == 0
            row = Recording(
                stream_id=stream_id,
                status="recording",
                start_time=datetime.now(timezone.utc),
            )
            session.add(row)
            session.commit()
            self.launch(row.id)
        self.starts += 1
        return True

    async def stop_recording(self, recording_id, *, reason):
        self.stop_attempts += 1
        assert reason == "automatic"
        assert self.database.sync_engine.pool.checkedout() == 0
        if self.fail_stop:
            raise RuntimeError("synthetic recording stop failure")
        process = self.active.pop(recording_id)
        process.stdin.write(b"x")
        process.stdin.flush()
        assert process.wait(timeout=5) == 0
        with self.database.sync_session_factory() as session:
            row = session.get(Recording, recording_id)
            assert session.get(Stream, row.stream_id).ended_at is not None
            row.status, row.end_time = "completed", datetime.now(timezone.utc)
            session.commit()
        self.stops += 1
        return True

    def close(self):
        for process in self.children:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()


@pytest.fixture
async def ctx(tmp_path, monkeypatch, request):
    denied = []
    for operation in ("connect", "connect_ex"):
        original = getattr(socket.socket, operation)

        def local_only(sock, address, original=original):
            if sock.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in (
                "127.0.0.1",
                "::1",
            ):
                denied.append("external connection blocked")
                raise AssertionError(
                    "External networking is forbidden in this contract"
                )
            return original(sock, address)

        monkeypatch.setattr(socket.socket, operation, local_only)

    provider_calls = []

    async def users(incoming):
        assert incoming.query.getall("id") == ["111"]
        provider_calls.append("users")
        return web.json_response(
            {
                "data": [
                    {
                        "id": "111",
                        "login": "fixture_channel",
                        "display_name": "Fixture Channel",
                        "type": "",
                        "broadcaster_type": "",
                        "description": "synthetic",
                        "profile_image_url": "",
                        "offline_image_url": "",
                        "view_count": 0,
                        "created_at": "2020-01-01T00:00:00Z",
                    }
                ]
            }
        )

    async def games(incoming):
        assert incoming.query.getall("id") == ["fixture-game"]
        provider_calls.append("games")
        return web.json_response(
            {
                "data": [
                    {
                        "id": "fixture-game",
                        "name": "Fixture Game",
                        "box_art_url": "",
                        "igdb_id": "",
                    }
                ]
            }
        )

    provider = web.Application()
    provider.router.add_get("/helix/users", users)
    provider.router.add_get("/helix/games", games)
    runner = web.AppRunner(provider)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'catalog.db'}")
    with database.sync_engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    with database.sync_session_factory() as session:
        if session.get(GlobalSettings, 1) is None:
            session.add(GlobalSettings(id=1, notifications_enabled=False))
            session.add(
                RecordingSettings(id=1, enabled=True, output_directory=str(tmp_path))
            )
            session.add(
                Streamer(
                    id=1,
                    twitch_id="111",
                    username="fixture_channel",
                    title="Before",
                    is_live=False,
                )
            )
            session.flush()
            session.add(StreamerRecordingSettings(streamer_id=1, enabled=True))
            session.commit()
    settings = Settings(
        ENVIRONMENT="test",
        TWITCH_APP_ID="fixture-client",
        TWITCH_APP_SECRET="fixture-only",
        EVENTSUB_SECRET="synthetic-eventsub-contract-key",
        BASE_URL="https://localhost:8000",
        RECORDING_DIRECTORY=str(tmp_path / "recordings"),
        ARTWORK_BASE_PATH=str(tmp_path / "artwork"),
        _env_file=None,
    )
    app = create_app(settings=settings, database=database)
    recorder = ControlledRecorder(database)
    app.state.recording_manager = recorder
    app.state.twitch_api = TwitchAPIService(settings=settings)
    app.state.twitch_api.base_url = f"http://127.0.0.1:{runner.addresses[0][1]}/helix"
    app.state.twitch_api._access_token = "synthetic-provider-token"
    app.state.twitch_api._token_expires_at = float("inf")
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    registry = await dependencies.get_application_event_registry(connection)
    trace = {"node": request.node.name}
    value = SimpleNamespace(
        app=app,
        database=database,
        recorder=recorder,
        registry=registry,
        connection=connection,
        trace=trace,
        provider_calls=provider_calls,
        armed=False,
        commit_attempts=0,
        session_attempts=0,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://localhost:8000"
        ) as client:
            value.client = client
            yield value
    finally:
        trace["network_denied"] = len(denied)
        trace["provider_calls"] = list(provider_calls)
        OBSERVATIONS.append(trace)
        recorder.close()
        await _close_application_images(app)
        await _close_application_twitch(app)
        await app.state.websocket_manager.close_all()
        assert database.sync_engine.pool.checkedout() == 0
        await database.adispose()
        await runner.cleanup()
        assert not denied


def seed(ctx, kind):
    if kind == "stream.online":
        return
    now = datetime.now(timezone.utc) - timedelta(hours=1)
    with ctx.database.sync_session_factory() as session:
        session.get(Streamer, 1).is_live = True
        session.add(
            Stream(
                id=1,
                streamer_id=1,
                twitch_stream_id="fixture-stream",
                title="Before",
                started_at=now,
            )
        )
        session.flush()
        if kind == "stream.offline":
            session.add(
                Recording(id=1, stream_id=1, status="recording", start_time=now)
            )
        session.commit()
    if kind == "stream.offline":
        ctx.recorder.launch(1)


def payload(kind):
    data = {
        "broadcaster_user_id": "111",
        "broadcaster_user_login": "fixture_channel",
        "broadcaster_user_name": "Fixture Channel",
    }
    if kind == "stream.online":
        data.update(
            id="fixture-stream",
            type="live",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
    elif kind == "channel.update":
        data.update(
            title="After",
            language="de",
            category_name="Fixture Game",
            category_id="fixture-game",
            content_classification_labels=[],
        )
    return {
        "subscription": {
            "id": "fixture-subscription",
            "type": kind,
            "version": "2" if kind == "channel.update" else "1",
            "status": "enabled",
            "cost": 0,
            "condition": {"broadcaster_user_id": "111"},
            "transport": {
                "method": "webhook",
                "callback": "https://localhost:8000/eventsub",
            },
            "created_at": "2020-01-01T00:00:00Z",
        },
        "event": data,
    }


def signed(ctx, body, *, kind="notification", age=0, bad_signature=False):
    raw = json.dumps(body, separators=(",", ":")).encode()
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=age)).isoformat()
    message_id = "same-synthetic-delivery"
    signature = hmac.new(
        (
            "incorrect-synthetic-key"
            if bad_signature
            else ctx.app.state.settings.EVENTSUB_SECRET
        ).encode(),
        message_id.encode() + timestamp.encode() + raw,
        hashlib.sha256,
    ).hexdigest()
    return {
        "content": raw,
        "headers": {
            "Content-Type": "application/json",
            "Twitch-Eventsub-Message-Id": message_id,
            "Twitch-Eventsub-Message-Type": kind,
            "Twitch-Eventsub-Message-Timestamp": timestamp,
            "Twitch-Eventsub-Message-Signature": "sha256=" + signature,
        },
    }


def state(ctx):
    with ctx.database.sync_session_factory() as session:
        streams = session.query(Stream).order_by(Stream.id).all()
        streamer = session.get(Streamer, 1)
        return {
            "stream_count": len(streams),
            "ended": sum(row.ended_at is not None for row in streams),
            "stream_titles": [row.title for row in streams],
            "live": streamer.is_live,
            "channel_title": streamer.title,
            "chapters": session.query(StreamEvent).count(),
            "categories": session.query(Category).count(),
            "recordings": [
                row.status for row in session.query(Recording).order_by(Recording.id)
            ],
            "start_attempts": ctx.recorder.start_attempts,
            "stop_attempts": ctx.recorder.stop_attempts,
            "starts": ctx.recorder.starts,
            "stops": ctx.recorder.stops,
            "children_created": len(ctx.recorder.children),
            "children_alive": sum(
                child.poll() is None for child in ctx.recorder.children
            ),
        }


def assert_effect(ctx, kind):
    result = state(ctx)
    assert result["stream_count"] == 1
    if kind == "stream.online":
        assert result["live"] is True and result["ended"] == 0
        assert result["recordings"] == ["recording"]
        assert (
            result["starts"]
            == result["children_created"]
            == result["children_alive"]
            == 1
        )
        assert result["chapters"] == 1
    elif kind == "stream.offline":
        assert result["live"] is False and result["ended"] == 1
        assert result["recordings"] == ["completed"]
        assert (
            result["stops"] == result["children_created"] == 1
            and result["children_alive"] == 0
        )
        assert result["chapters"] == 0
    else:
        assert result["channel_title"] == "After" and result["stream_titles"] == [
            "After"
        ]
        assert result["chapters"] == result["categories"] == 1
        assert result["children_created"] == 0


async def exercise(ctx, kind, fault=None, *, recreate_registry=False):
    seed(ctx, kind)
    ctx.armed = True
    actual_factory = ctx.database.sync_session_factory

    def open_session():
        ctx.session_attempts += 1
        if ctx.armed and fault == "session-open":
            raise SQLAlchemyError("synthetic session construction failure")
        return actual_factory()

    def before_commit(session):
        if not ctx.armed:
            return
        ctx.commit_attempts += 1
        if (fault == "first-commit" and ctx.commit_attempts == 1) or (
            fault == "category-commit" and ctx.commit_attempts == 3
        ):
            raise SQLAlchemyError("synthetic commit failure")

    ctx.registry._session_factory = open_session
    ctx.recorder.fail_start, ctx.recorder.fail_stop = fault == "start", fault == "stop"
    event.listen(ctx.database.sync_session_factory, "before_commit", before_commit)
    request = signed(ctx, payload(kind))
    try:
        first = await ctx.client.post("/eventsub", **request)
        ctx.trace.update(
            first_status=first.status_code, after_failure=state(ctx), fault=fault
        )
        ctx.armed = ctx.recorder.fail_start = ctx.recorder.fail_stop = False
        if recreate_registry:
            ctx.app.state.event_registry = None
            ctx.registry = await dependencies.get_application_event_registry(
                ctx.connection
            )
        retry = await ctx.client.post("/eventsub", **request)
        duplicate = await ctx.client.post("/eventsub", **request)
        ctx.trace.update(
            statuses=[first.status_code, retry.status_code, duplicate.status_code],
            final=state(ctx),
            commit_attempts=ctx.commit_attempts,
            session_attempts=ctx.session_attempts,
            registry_recreated=recreate_registry,
        )
        return first.status_code, retry.status_code, duplicate.status_code
    finally:
        event.remove(ctx.database.sync_session_factory, "before_commit", before_commit)


@pytest.mark.parametrize("kind,fault", FAULTS)
async def test_failed_core_delivery_is_retried_with_identical_message_id(
    ctx, kind, fault
):
    statuses = await exercise(ctx, kind, fault)
    assert statuses == (500, 204, 204)
    assert_effect(ctx, kind)


@pytest.mark.parametrize("kind,fault", FAULTS[-3:])
async def test_registry_recreation_after_partial_commit_preserves_single_effect(
    ctx, kind, fault
):
    statuses = await exercise(ctx, kind, fault, recreate_registry=True)
    assert statuses[1:] == (204, 204)
    assert_effect(ctx, kind)


@pytest.mark.parametrize("kind", KINDS)
async def test_successful_delivery_and_duplicates_keep_one_effect(ctx, kind):
    assert await exercise(ctx, kind) == (204, 204, 204)
    assert_effect(ctx, kind)


@pytest.mark.parametrize("kind", KINDS)
async def test_optional_alert_failure_does_not_repeat_core_work(ctx, kind, monkeypatch):
    with ctx.database.sync_session_factory() as session:
        settings = session.get(GlobalSettings, 1)
        settings.notifications_enabled = True
        settings.notify_online_global = settings.notify_offline_global = (
            settings.notify_update_global
        ) = True
        session.commit()
    attempts = []

    async def unavailable(*args, **kwargs):
        attempts.append(True)
        raise OSError("synthetic optional transport failure")

    monkeypatch.setattr(
        ctx.registry.notification_service.dispatcher.external_service,
        "send_stream_notification",
        unavailable,
    )
    assert await exercise(ctx, kind) == (204, 204, 204)
    ctx.trace["optional_transport_attempts"] = len(attempts)
    assert attempts == [True]
    assert_effect(ctx, kind)


@pytest.mark.parametrize("boundary", ("bad-signature", "expired", "challenge"))
async def test_signature_age_and_challenge_controls(ctx, boundary):
    before = state(ctx)
    if boundary == "challenge":
        request = signed(
            ctx,
            {"challenge": "synthetic-challenge"},
            kind="webhook_callback_verification",
        )
    else:
        request = signed(
            ctx,
            payload("stream.online"),
            age=11 if boundary == "expired" else 0,
            bad_signature=boundary == "bad-signature",
        )
    response = await ctx.client.post("/eventsub", **request)
    ctx.trace.update(status=response.status_code, unchanged=before == state(ctx))
    assert response.status_code == (200 if boundary == "challenge" else 403)
    if boundary == "challenge":
        assert response.text == "synthetic-challenge"
    assert before == state(ctx) and ctx.provider_calls == []


@pytest.mark.parametrize("kind", ("stream.online", "stream.offline"))
async def test_recorder_refusal_is_retryable(ctx, kind, monkeypatch):
    seed(ctx, kind)
    method = "start_recording" if kind == "stream.online" else "stop_recording"
    original = getattr(ctx.recorder, method)

    async def refuse(*args, **kwargs):
        return None if kind == "stream.online" else False

    monkeypatch.setattr(ctx.recorder, method, refuse)
    request = signed(ctx, payload(kind))
    assert (await ctx.client.post("/eventsub", **request)).status_code == 500
    monkeypatch.setattr(ctx.recorder, method, original)
    assert (await ctx.client.post("/eventsub", **request)).status_code == 204
    assert_effect(ctx, kind)


async def test_update_replay_after_registry_restart_keeps_distinct_delivery_history(
    ctx,
):
    seed(ctx, "channel.update")
    body = payload("channel.update")
    request = signed(ctx, body)
    assert (await ctx.client.post("/eventsub", **request)).status_code == 204
    ctx.app.state.event_registry = None
    ctx.registry = await dependencies.get_application_event_registry(ctx.connection)
    assert (await ctx.client.post("/eventsub", **request)).status_code == 204
    assert_effect(ctx, "channel.update")
    # Same content is a new history event when Twitch gives it another ID.
    request["headers"]["Twitch-Eventsub-Message-Id"] = "distinct-delivery"
    timestamp = request["headers"]["Twitch-Eventsub-Message-Timestamp"]
    request["headers"]["Twitch-Eventsub-Message-Signature"] = (
        "sha256="
        + hmac.new(
            ctx.app.state.settings.EVENTSUB_SECRET.encode(),
            b"distinct-delivery" + timestamp.encode() + request["content"],
            hashlib.sha256,
        ).hexdigest()
    )
    assert (await ctx.client.post("/eventsub", **request)).status_code == 204
    assert state(ctx)["chapters"] == 2


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("cancel", (False, True), ids=("timeout", "cancel"))
async def test_callback_drains_committing_worker_before_retry(
    ctx, kind, cancel, monkeypatch
):
    import asyncio
    from threading import Event
    from app.routes import eventsub

    seed(ctx, kind)
    entered, release, finished = Event(), Event(), Event()
    armed = True

    def after_commit(session):
        nonlocal armed
        if armed:
            armed = False
            entered.set()
            assert release.wait(10)
            finished.set()

    original_timeouts = eventsub.TIMEOUTS
    event.listen(ctx.database.sync_session_factory, "after_commit", after_commit)
    if not cancel:
        from dataclasses import replace

        monkeypatch.setattr(
            eventsub, "TIMEOUTS", replace(eventsub.TIMEOUTS, EVENT_HANDLER_TIMEOUT=0.1)
        )
    request = signed(ctx, payload(kind))
    task = asyncio.create_task(ctx.client.post("/eventsub", **request))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if cancel:
            task.cancel()
        else:
            await asyncio.sleep(0.2)
        assert not task.done() and not finished.is_set()
        # In-flight duplicate must not dispatch another worker/process.
        assert (await ctx.client.post("/eventsub", **request)).status_code == 204
        release.set()
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert (await task).status_code == 500
        assert finished.is_set()
        assert ctx.database.sync_engine.pool.checkedout() == 0
        monkeypatch.setattr(eventsub, "TIMEOUTS", original_timeouts)
        assert (await ctx.client.post("/eventsub", **request)).status_code == 204
        assert_effect(ctx, kind)
    finally:
        release.set()
        if not task.done():
            await asyncio.gather(task, return_exceptions=True)
        event.remove(ctx.database.sync_session_factory, "after_commit", after_commit)


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", [False, True])
async def test_update_retry_keeps_original_stream_after_offline(ctx, replacement):
    seed(ctx, "channel.update")
    request = signed(ctx, payload("channel.update"))
    commits = 0

    def fail_chapter(session):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise SQLAlchemyError("chapter commit unavailable")

    event.listen(ctx.database.sync_session_factory, "before_commit", fail_chapter)
    try:
        assert (await ctx.client.post("/eventsub", **request)).status_code == 500
    finally:
        event.remove(ctx.database.sync_session_factory, "before_commit", fail_chapter)
    assert (
        await ctx.client.post("/eventsub", **signed(ctx, payload("stream.offline")))
    ).status_code == 204
    if replacement:
        replacement_time = datetime.fromisoformat(
            request["headers"]["Twitch-Eventsub-Message-Timestamp"]
        ) + timedelta(seconds=1)
        with ctx.database.sync_session_factory() as session:
            session.add(
                Stream(
                    id=2,
                    streamer_id=1,
                    twitch_stream_id="replacement",
                    started_at=replacement_time,
                    title="Replacement",
                )
            )
            session.get(Streamer, 1).title = "Replacement"
            session.commit()
    assert (await ctx.client.post("/eventsub", **request)).status_code == 204
    assert (await ctx.client.post("/eventsub", **request)).status_code == 204
    with ctx.database.sync_session_factory() as session:
        chapter = session.query(StreamEvent).one()
        assert chapter.stream_id == 1 and chapter.title == "After"
        assert chapter.delivery_key is not None
        assert session.get(Stream, 1).ended_at is not None
        assert session.query(Stream).count() == (2 if replacement else 1)
        if replacement:
            assert session.get(Stream, 2).title == "Replacement"
            assert session.get(Streamer, 1).title == "Replacement"


@pytest.mark.asyncio
async def test_offline_emitted_before_local_recording_start_stops_owned_child(
    ctx, monkeypatch
):
    import asyncio
    from app.utils.async_db_utils import run_in_thread_pool
    from tests.test_processing_callback_ownership import close_owned

    ctx.app.state.recording_manager = None
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager, ctx.connection
    )
    ctx.registry.recording_service = manager
    lifecycle = manager.orchestrator.lifecycle_manager
    children = []

    async def spawn(**kwargs):
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import sys; print('ready', flush=True); sys.stdin.buffer.read()",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        children.append(child)
        assert await child.stdout.readline() == b"ready\n"
        manager.process_manager.active_processes[f"stream_{kwargs['stream'].id}"] = child
        return child

    async def monitor(recording_id):
        await asyncio.Event().wait()

    monkeypatch.setattr(manager.process_manager, "start_recording_process", spawn)
    monkeypatch.setattr(lifecycle, "monitor_and_process_recording", monitor)
    online_body = payload("stream.online")
    online_body["event"]["started_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    online_request = signed(ctx, online_body)
    # Both emissions precede delayed local admission; only stream identity is stable.
    offline_request = signed(ctx, payload("stream.offline"))
    try:
        assert (await ctx.client.post("/eventsub", **online_request)).status_code == 204
        assert len(children) == 1 and children[0].returncode is None
        with ctx.database.sync_session_factory() as session:
            start = session.query(Recording).one().start_time.replace(tzinfo=timezone.utc)
            emitted = datetime.fromisoformat(
                offline_request["headers"]["Twitch-Eventsub-Message-Timestamp"]
            )
            assert start > emitted
        assert (await ctx.client.post("/eventsub", **offline_request)).status_code == 204
        assert (await ctx.client.post("/eventsub", **offline_request)).status_code == 204
        assert children[0].returncode is not None
        assert len(children) == 1
        with ctx.database.sync_session_factory() as session:
            assert session.query(Recording).one().status == "stopped"
            assert session.query(Stream).one().ended_at is not None
            assert session.query(StreamEvent).count() == 1
        assert lifecycle._postprocessing_scheduled == {1}
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        await close_owned([ctx.app])


@pytest.mark.parametrize(
    "fault",
    [
        "raise",
        "false",
        "db-commit",
        "db-replacement",
        "cancel",
        "timeout",
        "dead",
        "start",
        "create-cancel",
        "lost-state",
        "durable-owner",
        "stop-commit-cancel",
        "state-cancel",
        "replacement-live",
        "new-stream",
        "online-session",
        "online-commit",
        "offline-session",
        "offline-commit",
        "update-session",
        "update-commit",
    ],
)
async def test_real_manager_offline_retry_stops_child_after_termination_failure(
    ctx, monkeypatch, fault
):
    import asyncio
    from app.utils.async_db_utils import run_in_thread_pool
    from tests.test_processing_callback_ownership import close_owned

    ctx.app.state.recording_manager = None
    manager = await run_in_thread_pool(
        dependencies.get_application_recording_manager, ctx.connection
    )
    ctx.registry.recording_service = manager
    lifecycle = manager.orchestrator.lifecycle_manager
    children = []
    armed = True
    entered = asyncio.Event()
    native_terminate = manager.process_manager.terminate_process
    release_termination = asyncio.Event()
    catalog_fault = False
    actual_factory = ctx.database.sync_session_factory

    def open_catalog_session():
        if catalog_fault and fault.endswith("-session"):
            raise SQLAlchemyError("synthetic catalog session construction failure")
        return actual_factory()

    ctx.registry._session_factory = open_catalog_session
    from app.routes import eventsub

    original_timeouts = eventsub.TIMEOUTS
    from threading import Event

    committed, release_commit = Event(), Event()

    def observe_recording_flush(session, _):
        if any(isinstance(row, Recording) for row in session.new):
            session.info["recording_inserted"] = True
        if any(
            isinstance(row, Recording) and row.status == "stopped"
            for row in session.dirty
        ):
            session.info["recording_stopped"] = True

    def hold_recording_commit(session):
        if (
            fault == "stop-commit-cancel"
            and armed
            and session.info.pop("recording_stopped", False)
        ):
            committed.set()
            assert release_commit.wait(10)
        if (
            fault == "create-cancel"
            and armed
            and session.info.pop("recording_inserted", False)
        ):
            committed.set()
            assert release_commit.wait(10)

    async def spawn(**kwargs):
        if armed and fault == "state-cancel":
            entered.set()
            await asyncio.Event().wait()
        if armed and fault == "start":
            return None
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import sys; print('ready', flush=True); sys.stdin.buffer.read()",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        children.append(child)
        assert await child.stdout.readline() == b"ready\n"
        manager.process_manager.active_processes[f"stream_{kwargs['stream'].id}"] = (
            child
        )
        return child

    async def terminate(process_id, *, recording_id):
        assert process_id == (
            f"stream_{recording_id}" if fault == "new-stream" else "stream_1"
        )
        assert recording_id in ({1, 2} if fault == "new-stream" else {1})
        if armed and fault in {"cancel", "timeout"}:
            entered.set()
            if fault == "timeout":
                # Expire at the controlled I/O boundary, not during catalog setup.
                await asyncio.wait_for(release_termination.wait(), 0.1)
            else:
                await release_termination.wait()
        if armed and fault in {"raise", "replacement-live", "new-stream"}:
            raise OSError("synthetic termination boundary unavailable")
        if armed and fault == "false":
            return False
        return await native_terminate(process_id, recording_id=recording_id)

    def fail_stop_commit(session):
        if catalog_fault and fault.endswith("-commit"):
            raise SQLAlchemyError("synthetic catalog first commit failure")
        if (
            armed
            and fault in {"db-commit", "db-replacement"}
            and any(
                isinstance(row, Recording) and row.status == "stopped"
                for row in session.dirty
            )
        ):
            raise SQLAlchemyError("synthetic stop status commit failure")

    async def monitor(recording_id):
        await asyncio.Event().wait()

    monkeypatch.setattr(manager.process_manager, "start_recording_process", spawn)
    monkeypatch.setattr(manager.process_manager, "terminate_process", terminate)
    monkeypatch.setattr(lifecycle, "monitor_and_process_recording", monitor)
    event.listen(ctx.database.sync_session_factory, "before_commit", fail_stop_commit)
    event.listen(
        ctx.database.sync_session_factory, "after_commit", hold_recording_commit
    )
    event.listen(
        ctx.database.sync_session_factory, "after_flush", observe_recording_flush
    )
    try:
        online_request = signed(ctx, payload("stream.online"))
        if fault in {"create-cancel", "state-cancel"}:
            task = asyncio.create_task(ctx.client.post("/eventsub", **online_request))
            if fault == "create-cancel":
                assert await asyncio.to_thread(committed.wait, 5)
            else:
                await asyncio.wait_for(entered.wait(), 5)
            task.cancel()
            release_commit.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            armed = False
            assert (
                await ctx.client.post("/eventsub", **online_request)
            ).status_code == 204
            assert len(children) == 1 and children[0].returncode is None
            with ctx.database.sync_session_factory() as session:
                assert session.query(Recording).count() == 1
                assert session.query(Stream).count() == 1
                assert session.query(StreamEvent).count() == 1
            return
        catalog_fault = fault.startswith("online-")
        online = await ctx.client.post("/eventsub", **online_request)
        assert online.status_code == (500 if fault == "start" or catalog_fault else 204)
        if fault == "start" or catalog_fault:
            if catalog_fault:
                assert children == []
                with actual_factory() as session:
                    assert session.query(Stream).count() == 0
                    assert session.query(Recording).count() == 0
            catalog_fault = False
            armed = False
            assert (
                await ctx.client.post("/eventsub", **online_request)
            ).status_code == 204
            assert (
                await ctx.client.post("/eventsub", **online_request)
            ).status_code == 204
            with ctx.database.sync_session_factory() as session:
                assert session.query(Recording).count() == 1
                assert session.query(Stream).count() == 1
                assert session.query(StreamEvent).count() == 1
            assert len(children) == 1 and children[0].returncode is None
            return
        assert len(children) == 1 and children[0].returncode is None
        saved_state = None
        if fault.startswith("update-"):
            update_request = signed(ctx, payload("channel.update"))
            catalog_fault = True
            assert (
                await ctx.client.post("/eventsub", **update_request)
            ).status_code == 500
            catalog_fault = False
            assert (
                await ctx.client.post("/eventsub", **update_request)
            ).status_code == 204
            assert (
                await ctx.client.post("/eventsub", **update_request)
            ).status_code == 204
            assert len(children) == 1 and children[0].returncode is None
            with actual_factory() as session:
                assert (
                    session.query(Stream).count()
                    == session.query(Recording).count()
                    == 1
                )
                chapter = (
                    session.query(StreamEvent)
                    .filter_by(event_type="channel.update")
                    .one()
                )
                assert chapter.stream_id == 1 and chapter.title == "After"
                assert session.query(Category).count() == 1
            return
        if fault in {"lost-state", "durable-owner"}:
            saved_state = lifecycle.state_manager.remove_active_recording(1)
        if fault == "durable-owner":
            from app.models import ActiveRecordingState

            now = datetime.now(timezone.utc)
            with ctx.database.sync_session_factory() as session:
                session.add(
                    ActiveRecordingState(
                        stream_id=1,
                        recording_id=1,
                        process_id=children[0].pid,
                        process_identifier="synthetic-owner",
                        streamer_name="fixture_channel",
                        started_at=now,
                        ts_output_path=saved_state["file_path"],
                        status="active",
                        last_heartbeat=now,
                    )
                )
                session.commit()
            ctx.registry._processed_events.clear()
            assert (
                await ctx.client.post("/eventsub", **online_request)
            ).status_code == 500
        # A distinct event type gives offline its own fingerprint, re-used on retry.
        catalog_fault = fault.startswith("offline-")
        request = signed(ctx, payload("stream.offline"))
        if fault == "dead":
            children[0].terminate()
            await children[0].wait()
        if fault == "stop-commit-cancel":
            task = asyncio.create_task(ctx.client.post("/eventsub", **request))
            assert await asyncio.to_thread(committed.wait, 5)
            task.cancel()
            release_commit.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert children[0].returncode is not None
            with ctx.database.sync_session_factory() as session:
                assert session.query(Recording).one().status == "stopped"
            assert not lifecycle.state_manager.get_active_recordings()
            assert lifecycle._postprocessing_scheduled == {1}
            armed = False
        elif fault in {"cancel", "timeout"}:
            task = asyncio.create_task(ctx.client.post("/eventsub", **request))
            await asyncio.wait_for(entered.wait(), 5)
            if fault == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                assert (await task).status_code == 500
        else:
            assert (await ctx.client.post("/eventsub", **request)).status_code == (
                204 if fault == "dead" else 500
            )
        if fault not in {"db-commit", "db-replacement", "dead", "stop-commit-cancel"}:
            assert children[0].returncode is None
        if fault not in {"dead", "stop-commit-cancel"}:
            with ctx.database.sync_session_factory() as session:
                assert session.query(Recording).one().status == "recording"
            if saved_state is None:
                assert lifecycle.state_manager.get_active_recordings()
            assert not lifecycle._postprocessing_scheduled
        armed = False
        catalog_fault = False
        if saved_state is not None:
            lifecycle.state_manager.add_active_recording(1, saved_state)
        if fault == "durable-owner":
            with ctx.database.sync_session_factory() as session:
                session.query(ActiveRecordingState).delete()
                session.commit()
        if fault == "db-replacement":
            await spawn(stream=SimpleNamespace(id=1))
        if fault == "replacement-live":
            await spawn(stream=SimpleNamespace(id=1))
            manager.process_manager.long_stream_processes["stream_1"] = {
                "recording_id": 999,
                "monitor_task": None,
            }
            assert (await ctx.client.post("/eventsub", **request)).status_code == 500
            assert children[0].returncode is None and children[1].returncode is None
            manager.process_manager.long_stream_processes.pop("stream_1")
            manager.process_manager.active_processes["stream_1"] = children[0]
        if fault == "new-stream":
            replacement_time = datetime.fromisoformat(
                request["headers"]["Twitch-Eventsub-Message-Timestamp"]
            ) + timedelta(seconds=1)
            with ctx.database.sync_session_factory() as session:
                session.add(
                    Stream(
                        id=2,
                        streamer_id=1,
                        twitch_stream_id="replacement-stream",
                        started_at=replacement_time,
                    )
                )
                session.flush()
                session.add(
                    Recording(
                        id=2,
                        stream_id=2,
                        status="recording",
                        start_time=replacement_time,
                        path=str(
                            Path(ctx.app.state.settings.RECORDING_DIRECTORY)
                            / "replacement.ts"
                        ),
                    )
                )
                session.get(Streamer, 1).is_live = True
                session.commit()
            await spawn(stream=SimpleNamespace(id=2))
            lifecycle.state_manager.add_active_recording(
                2, {"stream_id": 2, "streamer_id": 1, "file_path": "replacement.ts"}
            )
        monkeypatch.setattr(eventsub, "TIMEOUTS", original_timeouts)
        assert (await ctx.client.post("/eventsub", **request)).status_code == 204
        assert (await ctx.client.post("/eventsub", **request)).status_code == 204
        assert children[0].returncode is not None
        if fault == "new-stream":
            assert len(children) == 2 and children[1].returncode is None
            with ctx.database.sync_session_factory() as session:
                assert session.get(Stream, 2).ended_at is None
                assert session.get(Streamer, 1).is_live is True
                assert session.get(Recording, 1).status == "stopped"
                assert session.get(Recording, 2).status == "recording"
            assert lifecycle._postprocessing_scheduled == {1}
            return
        assert len(children) == (
            2 if fault in {"db-replacement", "replacement-live"} else 1
        )
        if fault in {"db-replacement", "replacement-live"}:
            assert children[1].returncode is None
        assert not lifecycle.state_manager.get_active_recordings()
        with ctx.database.sync_session_factory() as session:
            assert session.query(Stream).count() == 1
            assert session.query(Recording).count() == 1
            assert session.query(Recording).one().status == "stopped"
    finally:
        armed = False
        catalog_fault = False
        release_termination.set()
        release_commit.set()
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        event.remove(
            ctx.database.sync_session_factory, "before_commit", fail_stop_commit
        )
        event.remove(
            ctx.database.sync_session_factory, "after_commit", hold_recording_commit
        )
        event.remove(
            ctx.database.sync_session_factory, "after_flush", observe_recording_flush
        )
        await close_owned([ctx.app])
