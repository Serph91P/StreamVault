"""Synchronous-only routes use FastAPI's native worker dispatch, not the loop."""

from importlib import import_module
import asyncio
from threading import Event
from sqlalchemy import event
from inspect import iscoroutinefunction
from threading import get_ident

import pytest

from app.models import StreamerRecordingSettings
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications

# Fixed affected surfaces, not a scan that silently stops testing migrated handlers.
SYNC_HANDLERS = {
    "admin": (
        "debug_videos_database",
        "debug_check_stream_recordings",
        "get_share_tokens_stats",
        "cleanup_share_tokens",
        "delete_share_token",
    ),
    "api_keys": ("list_api_keys", "create_api_key", "revoke_api_key"),
    "auth": ("get_onboarding_state", "complete_onboarding"),
    "notifications": (
        "mark_notifications_read",
        "clear_notifications",
        "get_notification_state",
    ),
    "push": (
        "subscribe_to_push",
        "unsubscribe_from_push",
        "send_test_notification",
        "get_push_debug_info",
    ),
    "recording": (
        "update_streamer_recording_settings",
        "update_streamer_cleanup_policy",
    ),
    "recordings": ("get_latest_recording", "get_recent_recordings"),
    "streamers": (
        "get_streamer",
        "update_streamer_settings",
        "get_streams_by_streamer_id",
        "get_stream_chapters",
    ),
    "videos": (
        "get_videos",
        "generate_share_token",
        "get_video_thumbnail",
        "stream_video_by_id",
        "get_video_chapters",
        "stream_video",
        "check_stream_has_recording",
        "check_multiple_streams_recordings",
        "debug_videos_database",
    ),
}


@pytest.mark.parametrize(
    "module,name",
    [(module, name) for module, names in SYNC_HANDLERS.items() for name in names],
)
def test_sync_handler_selects_the_native_fastapi_worker_branch(module, name):
    endpoint = getattr(import_module("app.routes." + module), name)
    assert iscoroutinefunction(endpoint) is False, (
        f"{module}.{name} would run blocking work on the request loop"
    )


_OWNER = object()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,field,expected,table",
    [
        ("/api/notifications/state", ("unread_count",), 0, "notification_state"),
        ("/api/recordings/latest", ("recording",), None, "recordings"),
        ("/api/recordings/recent", ("recordings",), [], "recordings"),
        ("/auth/onboarding-state", ("welcome_completed",), False, "system_state"),
        ("/api/api-keys", (), [], "api_keys"),
        ("/api/streamers/streamer/1", ("username",), _OWNER, "streamers"),
        ("/api/streamers/1/streams", ("streamer", "username"), _OWNER, "streamers"),
        ("/api/videos", (), [], "streams"),
        ("/api/admin/share-tokens/stats", ("data", "total_tokens"), 0, "share_tokens"),
    ],
)
async def test_authenticated_sync_catalogue_reads_are_off_loop_in_both_real_factories(
    image_applications, path, field, expected, table
):
    _, databases, clients, queries = image_applications
    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get(path)
        assert response.status_code == 200
        value = response.json()
        for component in field:
            value = value[component]
        assert value == (f"owner-{index}" if expected is _OWNER else expected)
        assert any(f"FROM {table}" in sql for _, sql in queries), (
            "handler must query its own catalogue, not merely authenticate against it"
        )
        assert queries and get_ident() not in [thread for thread, _ in queries]
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_sync_notification_and_cleanup_writes_persist_only_in_the_owner(
    image_applications,
):
    _, databases, clients, queries = image_applications
    queries.clear()
    marked = await clients[0].post(
        "/api/notifications/mark-read", json={"timestamp": "2026-01-01T12:00:00+00:00"}
    )
    assert marked.status_code == 200 and marked.json()["success"] is True
    saved = await clients[0].post(
        "/api/recording/streamers/1/cleanup-policy",
        json={"use_global_cleanup_policy": True},
    )
    assert saved.status_code == 200 and saved.json()["status"] == "success"
    assert queries and get_ident() not in [thread for thread, _ in queries]
    state = await clients[0].get("/api/notifications/state")
    peer = await clients[1].get("/api/notifications/state")
    assert state.json()["last_read_timestamp"].startswith("2026-01-01T12:00:00")
    assert peer.json()["last_read_timestamp"] is None

    def read(database):
        with database.sync_session_factory() as session:
            row = (
                session.query(StreamerRecordingSettings)
                .filter_by(streamer_id=1)
                .first()
            )
            return (row.use_global_cleanup_policy, row.cleanup_policy) if row else None

    assert await run_in_thread_pool(read, databases[0]) == (True, None)
    assert await run_in_thread_pool(read, databases[1]) is None
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/recordings/latest",
        "/api/status/active-recordings",
        "/api/recording/active",
        "/api/health",
        "/api/health/ready",
    ],
)
async def test_cancelled_http_worker_drains_before_its_request_session_closes(
    image_applications,
    path,
):
    _, databases, clients, _ = image_applications
    entered, release = Event(), Event()
    loop_thread = get_ident()

    def hold(connection, cursor, sql, *args):
        if (
            "FROM recordings" in sql or sql.strip() == "SELECT 1"
        ) and not entered.is_set():
            assert get_ident() != loop_thread
            entered.set()
            assert release.wait(5), "test did not release its held SQL callback"

    event.listen(databases[0].sync_engine, "before_cursor_execute", hold)
    task = asyncio.create_task(clients[0].get(path))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "request cleanup must wait for its database worker"
        assert databases[0].sync_engine.pool.checkedout() == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        event.remove(databases[0].sync_engine, "before_cursor_execute", hold)
