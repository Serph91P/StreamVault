"""Real ASGI WebSocket frames stay within their factory's connection manager."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import json
from pathlib import Path
from secrets import token_urlsafe

import httpx
from pydantic import SecretStr
import pytest
from starlette.types import ASGIApp, Message, Scope

from app.config.settings import get_settings
from app.database import Base
from app.main import create_app


@asynccontextmanager
async def socket_frames(
    app: ASGIApp, cookie: str, client_ip: str = "127.0.0.1"
) -> AsyncIterator[asyncio.Queue[Message]]:
    incoming: asyncio.Queue[Message] = asyncio.Queue()
    outgoing: asyncio.Queue[Message] = asyncio.Queue()
    scope: Scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "scheme": "wss",
        "path": "/ws",
        "raw_path": b"/ws",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"localhost:8000"), (b"cookie", cookie.encode())],
        "client": (client_ip, 12345),
        "server": ("localhost", 8000),
        "subprotocols": [],
    }
    await incoming.put({"type": "websocket.connect"})

    async def serve() -> None:
        await app(scope, incoming.get, outgoing.put)

    task = asyncio.create_task(serve())
    try:
        assert (await asyncio.wait_for(outgoing.get(), 3))["type"] == "websocket.accept"
        initial = await asyncio.wait_for(outgoing.get(), 3)
        assert initial["type"] == "websocket.send"
        assert json.loads(initial["text"])["type"] == "connection.status"
        yield outgoing
    finally:
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(task, 3)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_factory_websocket_frames_and_close_do_not_cross_contexts(
    tmp_path: Path,
) -> None:
    configs = [
        get_settings().model_copy(
            update={
                "database_url": SecretStr(f"sqlite:///{tmp_path / (name + '.db')}"),
                "auth_jwt_secret": SecretStr(token_urlsafe(48)),
                "RECORDING_DIRECTORY": str(tmp_path / name),
            }
        )
        for name in ("ws-first", "ws-second")
    ]
    apps = [create_app(settings=config) for config in configs]
    cookies = []
    try:
        for app in apps:
            with app.state.database_lifecycle.sync_engine.begin() as connection:
                Base.metadata.create_all(connection)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://localhost:8000",
            ) as client:
                response = await client.post(
                    "/auth/setup",
                    json={"username": "ws-admin", "password": token_urlsafe(32)},
                )
                assert response.status_code == 200
                cookies.append(
                    "; ".join(
                        f"{name}={value}" for name, value in client.cookies.items()
                    )
                )
        first, second = (app.state.websocket_manager for app in apps)
        async with (
            socket_frames(apps[0], cookies[0]) as first_frames,
            socket_frames(apps[1], cookies[1], "127.0.0.2") as second_frames,
        ):
            assert len(first.active_connections) == len(second.active_connections) == 1
            for app, cookie, ip in zip(
                apps, cookies, ("127.0.0.1", "127.0.0.2"), strict=True
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="https://localhost:8000",
                ) as client:
                    response = await client.get(
                        "/admin/websocket-connections", headers={"cookie": cookie}
                    )
                    assert response.status_code == 200
                    assert response.json()["total_connections"] == 1
                    assert [
                        connection["real_ip"]
                        for connection in response.json()["connections"]
                    ] == [ip]
            await first.send_notification(
                {"type": "scope.first", "data": {"scope": "first"}}
            )
            frame = await asyncio.wait_for(first_frames.get(), 3)
            assert json.loads(frame["text"])["type"] == "scope.first"
            assert second_frames.empty()
            assert await second.get_events_since() == []
            await first.close_all()
            assert (await asyncio.wait_for(first_frames.get(), 3))[
                "type"
            ] == "websocket.close"
            assert not first.active_connections and not first._sender_tasks
            assert len(second.active_connections) == 1
            await second.send_notification(
                {"type": "scope.second", "data": {"scope": "second"}}
            )
            frame = await asyncio.wait_for(second_frames.get(), 3)
            assert json.loads(frame["text"])["type"] == "scope.second"
        assert not first._sender_tasks and not second._sender_tasks
    finally:
        for app in apps:
            await app.state.websocket_manager.close_all()
            await app.state.database_lifecycle.adispose()
