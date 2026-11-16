"""Authentication closes its worker scope before HTTP/WS work or cancellation."""

import asyncio
from threading import Event, get_ident

import pytest
from sqlalchemy import event

from app.middleware.auth import AuthMiddleware
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


def authenticated_scope(client, protocol):
    return {
        "type": protocol,
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https" if protocol == "http" else "wss",
        "path": "/api/catalogue-probe" if protocol == "http" else "/ws",
        "query_string": b"",
        "headers": [
            (b"cookie", f"access_token={client.cookies.get('access_token')}".encode())
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 8000),
        "subprotocols": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["http", "websocket"])
async def test_authentication_sql_is_off_loop_and_closed_before_handler(
    image_applications, protocol
):
    applications, databases, clients, queries = image_applications
    messages = []
    reached = []

    async def handler(scope, receive, send):
        reached.append(scope["type"])
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        assert queries and all(thread != get_ident() for thread, _ in queries)
        if protocol == "http":
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})
        else:
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.close", "code": 1000})

    async def receive():
        return {
            "type": "websocket.connect" if protocol == "websocket" else "http.request"
        }

    async def send(message):
        messages.append(message)

    middleware = AuthMiddleware(
        handler,
        database=databases[0],
        settings_provider=lambda: applications[0].state.settings,
    )
    queries.clear()
    await middleware(authenticated_scope(clients[0], protocol), receive, send)
    assert reached == [protocol]
    assert messages[-1]["type"] == (
        "http.response.body" if protocol == "http" else "websocket.close"
    )
    if protocol == "http":
        assert messages[0]["status"] == 204
    else:
        assert messages[-1]["code"] == 1000


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["http", "websocket"])
async def test_cancelled_authentication_drains_the_actual_database_worker(
    image_applications, protocol
):
    applications, databases, clients, _ = image_applications
    entered, release = Event(), Event()
    reached = []

    def pause_sql(connection, cursor, statement, parameters, context, executemany):
        if "FROM users" in statement:
            entered.set()
            assert release.wait(5), "test SQL worker was not released"

    async def handler(scope, receive, send):
        reached.append(scope["type"])

    async def receive():
        return {
            "type": "websocket.connect" if protocol == "websocket" else "http.request"
        }

    async def send(message):
        raise AssertionError("cancelled authentication must not publish a response")

    middleware = AuthMiddleware(
        handler,
        database=databases[0],
        settings_provider=lambda: applications[0].state.settings,
    )
    event.listen(databases[0].sync_engine, "before_cursor_execute", pause_sql)
    task = asyncio.create_task(
        middleware(authenticated_scope(clients[0], protocol), receive, send)
    )
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        assert databases[0].sync_engine.pool.checkedout() == 1
        task.cancel()
        for _ in range(10):
            await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with asyncio.timeout(3):
            while databases[0].sync_engine.pool.checkedout():
                await asyncio.sleep(0.01)
        event.remove(databases[0].sync_engine, "before_cursor_execute", pause_sql)
    assert not reached
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
