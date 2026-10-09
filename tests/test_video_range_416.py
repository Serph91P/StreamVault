"""Regression coverage for authenticated stored-media range responses."""

from pathlib import Path

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
    media_file.write_bytes(b"synthetic-media")
    database = _Database(_Stream(media_file))

    async def valid_session(_self, _token):
        return True

    monkeypatch.setattr(videos.AuthService, "validate_session", valid_session)
    monkeypatch.setattr(videos, "validate_path_security", lambda path, _mode: path)
    monkeypatch.setattr(videos, "validate_file_type", lambda *_args: None)
    application = FastAPI()
    application.include_router(videos.router)
    application.dependency_overrides[dependencies.get_db] = lambda: database

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
