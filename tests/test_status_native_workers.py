"""Real status routes use native workers and their own application resources."""

import asyncio
from datetime import datetime, timedelta, timezone
from importlib import import_module
from inspect import iscoroutinefunction
from threading import get_ident

import pytest
from sqlalchemy import event
from app.models.background_task import BackgroundTask
from app.utils.async_db_utils import run_in_thread_pool

from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,field,expected",
    [
        ("recordings-active", ("active_count",), 1),
        ("active-recordings", ("count",), 1),
        ("system", ("system", "live_streamers"), 1),
        ("streamers", ("summary", "recording"), 1),
        ("streams", ("summary", "recorded_count"), 1),
        ("notifications", ("recent_events", 0, "streamer_name"), None),
    ],
)
async def test_status_populated_catalogue_preserves_owned_values(
    image_applications, path, field, expected
):
    from app.models import Recording, Stream, StreamEvent

    _, databases, clients, queries = image_applications
    started = datetime.now(timezone.utc) - timedelta(seconds=60)

    def seed(database, index):
        with database.sync_session_factory() as session:
            session.add(
                Stream(
                    id=71,
                    streamer_id=1,
                    title=f"title-{index}",
                    started_at=started,
                    created_at=started,
                )
            )
            session.flush()
            session.add(
                Recording(
                    id=72,
                    stream_id=71,
                    status="recording",
                    start_time=started,
                    path=f"/scope-{index}/recording.ts",
                )
            )
            session.add(
                StreamEvent(
                    stream_id=71,
                    event_type="stream_online",
                    title=f"title-{index}",
                    timestamp=started,
                )
            )
            session.commit()

    for index, database in enumerate(databases):
        await run_in_thread_pool(seed, database, index)
    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get(f"/api/status/{path}")
        assert response.status_code == 200, response.text
        body = response.json()
        value = body
        for part in field:
            value = value[part]
        assert value == (f"owner-{index}" if expected is None else expected)
        if path == "active-recordings":
            record = body["active_recordings"][0]
            assert record["streamer_name"] == f"owner-{index}"
            assert record["title"] == f"title-{index}"
            assert record["file_path"] == f"/scope-{index}/recording.ts"
            assert (
                60
                <= record["duration"]
                <= int((datetime.now(timezone.utc) - started).total_seconds()) + 1
            )
        assert queries and get_ident() not in [thread for thread, _ in queries]
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_status_nullable_legacy_creation_time_has_no_fabricated_last_seen(
    image_applications,
):
    """A persisted NULL timestamp must not turn the whole status response into500."""
    from sqlalchemy import update
    from app.models import Stream, StreamEvent

    _, databases, clients, queries = image_applications
    now = datetime.now(timezone.utc)

    def seed(database, index):
        with database.sync_session_factory() as session:
            session.add(
                Stream(id=71, streamer_id=1, title=f"own-{index}", created_at=now)
            )
            session.add(
                StreamEvent(stream_id=71, event_type="channel_update", timestamp=now)
            )
            session.flush()
            session.execute(
                update(Stream)
                .where(Stream.id == 71)
                .values(created_at=None if index == 0 else now)
            )
            session.execute(update(StreamEvent).values(timestamp=None))
            session.commit()

    for index, database in enumerate(databases):
        await run_in_thread_pool(seed, database, index)
    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get("/api/status/streamers")
        assert response.status_code == 200, response.text
        row = response.json()["streamers"][0]
        assert row["last_title"] == f"own-{index}"
        assert row["last_seen"] == (
            None if index == 0 else now.replace(tzinfo=None).isoformat()
        )
        notifications = await client.get("/api/status/notifications")
        assert notifications.status_code == 200
        assert notifications.json()["recent_events"] == []
        assert queries and get_ident() not in [thread for thread, _ in queries]
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.parametrize(
    "name",
    [
        "check_recordings_active",
        "get_system_status",
        "get_active_recordings_status",
        "get_background_queue_status",
        "get_health_status",
        "get_streamers_status",
        "get_streams_status",
        "get_notifications_status",
    ],
)
def test_sync_status_uses_native_dispatch(name):
    assert not iscoroutinefunction(getattr(import_module("app.routes.status"), name))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,table,expected_code",
    [
        ("recordings-active", "recordings", 500),
        ("active-recordings", "recordings", 500),
        ("system", "recordings", 500),
        ("streamers", "streamers", 500),
        ("streams", "streams", 500),
        ("notifications", "notification_settings", 500),
        ("notifications", "stream_events", 200),
    ],
)
async def test_status_query_failure_keeps_peer_and_closes_transactions(
    image_applications, path, table, expected_code
):
    _, databases, clients, _ = image_applications
    observed = []

    def unavailable(_connection, _cursor, statement, *_):
        if f"FROM {table}" in statement:
            observed.append(get_ident())
            raise RuntimeError("synthetic status query outage")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        failed = await clients[0].get(f"/api/status/{path}")
        peer = await clients[1].get(f"/api/status/{path}")
        assert failed.status_code == expected_code
        assert peer.status_code == 200
        assert "synthetic status query outage" not in failed.text
        if expected_code == 200:
            assert failed.json()["recent_events"] == []
        else:
            assert failed.json()["detail"].startswith("Failed")
        assert observed and get_ident() not in observed
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["system", "background-queue"])
async def test_status_queue_failure_is_explicit_and_owned(
    image_applications, monkeypatch, path
):
    apps, databases, clients, _ = image_applications
    observed = []

    def unavailable():
        observed.append(get_ident())
        raise RuntimeError("synthetic queue monitoring outage")

    monkeypatch.setattr(
        apps[0].state.background_queue_service, "get_queue_statistics", unavailable
    )
    failed = await clients[0].get(f"/api/status/{path}")
    peer = await clients[1].get(f"/api/status/{path}")
    assert peer.status_code == 200
    if path == "system":
        assert failed.status_code == 200
        assert failed.json()["background_queue"] == {
            "error": "Queue service unavailable"
        }
        assert failed.json()["system"]["total_streamers"] == 1
    else:
        assert failed.status_code == 500
        assert failed.json()["detail"] == "Failed to get background queue status"
    assert "synthetic queue monitoring outage" not in failed.text
    assert observed and get_ident() not in observed
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,field,expected,table",
    [
        ("/api/status/recordings-active", ("active_count",), 0, "recordings"),
        ("/api/status/system", ("system", "total_streamers"), 1, "streamers"),
        ("/api/status/active-recordings", ("count",), 0, "recordings"),
        ("/api/status/streamers", ("streamers", 0, "name"), None, "streamers"),
        ("/api/status/streams", ("summary", "recent_count"), 0, "streams"),
        ("/api/status/notifications", ("recent_events",), [], "stream_events"),
    ],
)
async def test_status_sql_is_owned_and_off_loop(
    image_applications, path, field, expected, table
):
    _, databases, clients, queries = image_applications
    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get(path)
        assert response.status_code == 200, response.text
        value = response.json()
        for part in field:
            value = value[part]
        assert value == (f"owner-{index}" if expected is None else expected)
        assert any(f"FROM {table}" in sql for _, sql in queries)
        assert get_ident() not in [thread for thread, _ in queries]
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/status/system", "/api/status/background-queue"])
async def test_status_queries_the_actual_owned_queue(
    image_applications, monkeypatch, path
):
    apps, databases, clients, queries = image_applications
    observed = []
    for index, app in enumerate(apps):
        queue = app.state.background_queue_service
        original = queue.get_queue_statistics

        def statistics(original=original, index=index):
            observed.append((index, get_ident()))
            return original()

        monkeypatch.setattr(queue, "get_queue_statistics", statistics)
    for client in clients:
        queries.clear()
        response = await client.get(path)
        assert response.status_code == 200, response.text
        assert get_ident() not in [thread for thread, _ in queries]
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    assert [index for index, _ in observed] == [0, 1]
    assert all(thread != get_ident() for _, thread in observed)


@pytest.mark.asyncio
async def test_status_health_queries_its_owner_and_keeps_peer_healthy(
    image_applications,
):
    _, databases, clients, queries = image_applications
    for client in clients:
        queries.clear()
        response = await client.get("/api/status/health")
        assert response.status_code == 200
        assert response.json()["components"]["database"] == "healthy"
        assert any(sql.strip() == "SELECT 1" for _, sql in queries)
        assert get_ident() not in [thread for thread, _ in queries]
    failed_probes = []

    def unavailable(_connection, _cursor, statement, *_):
        if statement.strip() == "SELECT 1":
            failed_probes.append(get_ident())
            raise RuntimeError("synthetic owned database outage")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        failed = await clients[0].get("/api/status/health")
        peer = await clients[1].get("/api/status/health")
        assert failed.json()["status"] == "degraded"
        assert failed.json()["components"]["database"] == "unhealthy"
        assert peer.json()["components"]["database"] == "healthy"
        assert failed_probes and get_ident() not in failed_probes
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)


@pytest.mark.asyncio
async def test_deferred_journal_work_is_counted_without_materializing_active_tasks(
    image_applications,
):
    apps, databases, clients, _ = image_applications
    queue = apps[0].state.background_queue_service

    async def retry_later(_payload, _progress):
        raise RuntimeError("synthetic retryable work failure")

    queue.register_task_handler("scope.deferred", retry_later)
    try:
        await queue.start()
        task_id = await queue.enqueue_task("scope.deferred", {"streamer_name": "scope"})

        async def deferred_snapshot():
            while True:
                response = await clients[0].get("/api/status/background-queue")
                assert response.status_code == 200
                data = response.json()
                if not data["active_tasks"] and data["stats"]["pending_tasks"] == 1:
                    return response
                await asyncio.sleep(0)

        owner = await asyncio.wait_for(deferred_snapshot(), 3)
        peer = await clients[1].get("/api/status/background-queue")
        assert owner.status_code == peer.status_code == 200
        assert owner.json()["active_tasks"] == []
        assert owner.json()["stats"]["pending_tasks"] == 1
        assert owner.json()["stats"]["queue_size"] == 1
        assert peer.json()["stats"]["pending_tasks"] == 0

        def persisted():
            with databases[0].sync_session_factory() as session:
                row = session.get(BackgroundTask, task_id)
                return row is not None and row.status == "retrying"

        assert await run_in_thread_pool(persisted)
        assert not queue.get_active_tasks()
    finally:
        await queue.stop()
        await queue.queue_manager.progress_tracker.cleanup_background_tasks()
