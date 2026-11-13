"""Regression coverage for authenticated stored-media range responses."""

from pathlib import Path
from contextlib import nullcontext

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient


class _Query:
    def __init__(self, stream):
        self._stream = stream

    def filter(self, *_args):
        return self

    def first(self):
        return self._stream


class _Database:
    def __init__(self, stream):
        self._stream = stream

    def query(self, _model):
        return _Query(self._stream)


class _Stream:
    id = 1
    title = "Synthetic recording"
    started_at = None
    ended_at = None

    def __init__(self, recording_path: Path):
        self.recording_path = str(recording_path)


@pytest.fixture
def stored_media_client(monkeypatch, tmp_path):
    from app import dependencies
    from app.routes import videos

    media_file = tmp_path / "recording.mp4"
    media_file.write_bytes(b"synthetic-media" * 10000)
    database = _Database(_Stream(media_file))

    def valid_session(_self, _token):
        return True

    monkeypatch.setattr(videos.AuthService, "resolve_legacy_session", valid_session)
    monkeypatch.setattr(videos, "SessionLocal", lambda: nullcontext(database))
    monkeypatch.setattr(videos, "validate_path_security", lambda path, _mode, *, recording_directory: path)
    monkeypatch.setattr(videos, "validate_file_type", lambda *_args: None)
    monkeypatch.setattr(
        videos, "validate_share_token", lambda token, *, db: 1 if token == "valid" else None
    )
    application = FastAPI()
    application.state.media_path = media_file
    application.include_router(videos.router)
    application.dependency_overrides[dependencies.get_db] = lambda: database
    application.dependency_overrides[dependencies.get_application_session_factory] = lambda: (lambda: nullcontext(database))

    def authenticated_media_identity(request: Request):
        if request.cookies.get("session") != "test-session":
            raise HTTPException(status_code=401, detail="Authentication required")
        return dependencies.AuthIdentity(
            subject="1",
            roles=frozenset(),
            scopes=frozenset(),
            auth_method="legacy-session",
            interactive=True,
        )

    application.dependency_overrides[dependencies.get_current_identity] = (
        authenticated_media_identity
    )

    client = TestClient(application)
    try:
        yield client, len(media_file.read_bytes())
    finally:
        client.close()
        application.dependency_overrides.pop(dependencies.get_db, None)
        application.dependency_overrides.pop(dependencies.get_current_identity, None)


def test_authenticated_stored_media_unsatisfied_range_has_content_range(
    stored_media_client,
):
    client, file_size = stored_media_client

    unauthenticated = client.get("/api/videos/1/stream")
    assert unauthenticated.status_code == 401

    partial = client.get(
        "/api/videos/1/stream",
        headers={"Range": "bytes=0-3"},
        cookies={"session": "test-session"},
    )
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 0-3/{file_size}"
    assert partial.content == b"synt"

    unsatisfied = client.get(
        "/api/videos/1/stream",
        headers={"Range": "bytes=999999999-"},
        cookies={"session": "test-session"},
    )
    assert unsatisfied.status_code == 416
    assert unsatisfied.headers["content-range"] == f"bytes */{file_size}"


def test_public_share_token_seek_and_expiry_keep_media_contract_fail_closed(
    stored_media_client, monkeypatch
):
    """Public links use synthetic file bytes, preserve seek headers, and fail closed."""
    from app.routes import videos

    client, file_size = stored_media_client
    monkeypatch.setattr(
        videos, "validate_share_token", lambda token, *, db: 1 if token == "valid" else None
    )

    def invalid_legacy_session(_self, _token):
        return None

    monkeypatch.setattr(videos.AuthService, "resolve_legacy_session", invalid_legacy_session)

    seek = client.get(
        "/api/videos/public/1?token=valid",
        headers={"Range": "bytes=4-8"},
    )
    unsatisfied = client.get(
        "/api/videos/public/1?token=valid",
        headers={"Range": "bytes=999999999-"},
    )
    expired = client.get("/api/videos/public/1?token=expired")

    assert seek.status_code == 206
    assert seek.headers["content-range"] == f"bytes 4-8/{file_size}"
    assert seek.content == b"hetic"
    assert unsatisfied.status_code == 416
    assert unsatisfied.headers["content-range"] == f"bytes */{file_size}"
    assert expired.status_code == 401


@pytest.mark.parametrize(
    "route", ["/api/videos/1/stream", "/api/videos/public/1?token=valid"]
)
def test_stored_media_uses_bounded_large_delivery_chunks(stored_media_client, route):
    client, _ = stored_media_client
    chunks = []

    class ObserveBody:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            async def observe(message):
                if message["type"] == "http.response.body":
                    chunks.append(len(message.get("body", b"")))
                await send(message)

            await self.app(scope, receive, observe)

    client.app.add_middleware(ObserveBody)
    client.cookies.set("session", "test-session")
    response = client.get(route)
    assert response.status_code == 200
    assert response.content == b"synthetic-media" * 10000
    assert response.headers["cache-control"] == "no-cache"
    assert max(chunks) == 65536
    assert sum(chunks) == len(response.content)
    suffix = client.get(route, headers={"Range": "bytes=-5"})
    assert suffix.status_code == 206
    assert suffix.content == response.content[-5:]
    assert (
        suffix.headers["content-range"]
        == f"bytes {len(response.content) - 5}-{len(response.content) - 1}/{len(response.content)}"
    )
    head = client.head(route)
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["content-length"] == str(len(response.content))


@pytest.mark.parametrize(
    "route", ["/api/videos/1/stream", "/api/videos/public/1?token=valid"]
)
def test_growing_full_media_over_real_uvicorn_has_exact_snapshot_length(
    stored_media_client, route
):
    import socket
    import threading
    import time
    import httpx
    import uvicorn

    client, size = stored_media_client
    app = client.app
    path = app.state.media_path
    original = path.read_bytes()

    class GrowingCapture:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            async def grow(message):
                if message["type"] == "http.response.start":
                    with path.open("ab") as writer:
                        writer.write(b"live capture continues" * 1000)
                await send(message)

            await self.app(scope, receive, grow)

    app.add_middleware(GrowingCapture)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]})
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        with httpx.Client(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            cookies={"session": "test-session"},
        ) as connection:
            response = connection.get(route)
            assert response.status_code == 200
            assert response.headers["content-length"] == str(size)
            assert response.content == original
            # More bytes exist on disk, but did not invalidate this snapshot transfer.
            assert path.stat().st_size > size
            selected = path.read_bytes()[10:101]
            ranged = connection.get(route, headers={"Range": "bytes=10-100"})
            assert ranged.status_code == 206
            assert ranged.content == selected
            assert ranged.headers["content-length"] == "91"
            before_head = path.stat().st_size
            head = connection.head(route)
            assert head.status_code == 200
            assert head.content == b""
            assert head.headers["content-length"] == str(before_head)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()
