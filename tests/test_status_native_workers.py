"""Real status routes use native workers and their own application resources."""

from importlib import import_module
from inspect import iscoroutinefunction
from threading import get_ident

import pytest
from sqlalchemy import event

from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


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
