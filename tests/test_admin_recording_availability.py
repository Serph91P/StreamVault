"""Authenticated repair must preserve media identity, not guess it from names."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.models import Recording, Stream, Streamer
import test_admin_authorization as auth_tests

admin_stack = auth_tests.admin_stack
credential_headers = auth_tests.credential_headers


@pytest.fixture
def repair(admin_stack, tmp_path):
    app, _, factory, _, _ = admin_stack
    headers = credential_headers(admin_stack, "jwt", "admin")
    client = TestClient(app)
    try:
        yield client, headers, factory, tmp_path
    finally:
        client.close()


def seed(repair, path=None, candidates=(), username="channel", stream_id=1):
    _, _, factory, _ = repair
    with factory() as db:
        streamer = db.query(Streamer).filter_by(username=username).first()
        if not streamer:
            streamer = Streamer(username=username, twitch_id=f"id-{username}")
            db.add(streamer)
            db.flush()
        stream = Stream(
            id=stream_id,
            streamer_id=streamer.id,
            title="shared adventure title",
            started_at=datetime.now(timezone.utc),
            recording_path=str(path) if path else None,
        )
        db.add(stream)
        db.flush()
        for candidate, status in candidates:
            db.add(
                Recording(
                    stream_id=stream.id,
                    path=str(candidate),
                    status=status,
                    start_time=datetime.now(timezone.utc),
                )
            )
        db.commit()
        return streamer.id


def request(repair, dry_run=False, **params):
    client, headers, _, _ = repair
    return client.post(
        "/api/admin/recordings/fix-availability",
        headers=headers,
        params={"dry_run": str(dry_run).lower(), **params},
    )


def stored(repair, stream_id=1):
    with repair[2]() as db:
        return db.get(Stream, stream_id).recording_path


@pytest.mark.parametrize(
    "suffix", [".mp4", ".ts", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v", ".m3u8"]
)
def test_preserve_existing_media_and_catalog_without_ts(repair, suffix):
    client, headers, _, root = repair
    media = root / f"completed{suffix}"
    media.write_bytes(b"synthetic media bytes, never modified")
    seed(repair, media)
    before = media.read_bytes()
    for dry_run in [True, False, False]:
        response = request(repair, dry_run)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["checked"] == 1 and data["fixed"] == data["errors"] == 0
        assert data["details"][0]["action"] == "none"
        assert stored(repair) == str(media)
        assert media.read_bytes() == before
    catalog = client.get("/api/stream/1/has-recording", headers=headers)
    assert catalog.status_code == 200
    assert catalog.json()["has_recording"] is True
    assert catalog.json()["file_path"] == str(media)


@pytest.mark.parametrize("old", [None, "missing.mp4", "directory"])
def test_only_unique_linked_recording_repairs_invalid_path_and_dry_run_agrees(
    repair, old
):
    root = repair[3]
    previous = root / old if old else None
    if old == "directory":
        previous.mkdir()
    media = root / "authoritative.mkv"
    media.write_bytes(b"linked media")
    seed(repair, previous, [(media, "completed"), (media, "completed")])
    dry = request(repair, True).json()
    assert stored(repair) == (str(previous) if previous else None)
    done = request(repair).json()
    assert dry["data"] == done["data"]
    assert dry["data"]["fixed"] == 1
    assert dry["data"]["details"][0]["action"] == ("update_path" if old else "set_path")
    assert stored(repair) == str(media)
    assert request(repair).json()["data"]["fixed"] == 0
    assert media.read_bytes() == b"linked media"


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "ambiguous",
        "active",
        "directory",
        "unlinked-names",
        "foreign-owner",
        "foreign-recording",
        "foreign-symlink",
    ],
)
def test_uncertain_media_never_changes_ownership(repair, case):
    root = repair[3]
    original = root / "missing-original.mp4"
    first = root / "shared_adventure_stream_1.ts"
    second = root / "shared_adventure_stream_10.ts"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    candidates = []
    if case == "ambiguous":
        candidates = [(first, "completed"), (second, "completed")]
    elif case == "active":
        candidates = [(first, "recording")]
    elif case == "directory":
        directory = root / "not-media.ts"
        directory.mkdir()
        candidates = [(directory, "completed")]
    elif case.startswith("foreign"):
        candidates = [(first, "completed")]
        foreign_path = first
        if case == "foreign-symlink":
            foreign_path = root / "alias.mp4"
            foreign_path.symlink_to(first)
        seed(
            repair,
            foreign_path if case != "foreign-recording" else None,
            [(foreign_path, "completed")] if case == "foreign-recording" else [],
            username="channel-extra",
            stream_id=10,
        )
    elif case == "missing":
        candidates = [(root / "missing.ts", "completed")]
    streamer_id = seed(repair, original, candidates)
    for dry_run in [True, False, False]:
        response = request(repair, dry_run, streamer_id=streamer_id)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["checked"] == 1 and data["fixed"] == data["errors"] == 0
        assert data["details"][0]["action"] == "none"
        assert stored(repair) == str(original)
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"


@pytest.mark.parametrize(
    "names",
    [
        ["shared_adventure.ts"],
        ["unrelated.ts"],
        ["stream_10.ts"],
        ["shared_adventure.ts", "shared_adventure_2.ts"],
    ],
)
def test_filesystem_name_and_date_matches_are_not_ownership(repair, monkeypatch, names):
    root = repair[3]
    files = []
    for name in names:
        media = root / name
        media.write_bytes(b"unassigned synthetic media")
        files.append(media)
    seed(repair)
    seed(repair, username="channel-extra", stream_id=10)
    original_exists = Path.exists
    original_rglob = Path.rglob

    # Redirect the old hardcoded scan to disposable files; never inspect real /recordings.
    def scan_exists(path, *args, **kwargs):
        if str(path).startswith("/recordings"):
            return True
        return original_exists(path, *args, **kwargs)

    def scan_rglob(path, pattern, *args, **kwargs):
        if str(path).startswith("/recordings"):
            return iter(files)
        return original_rglob(path, pattern, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", scan_exists)
    monkeypatch.setattr(Path, "rglob", scan_rglob)
    for dry_run in [True, False]:
        data = request(repair, dry_run).json()["data"]
        assert data["checked"] == 2
        assert data["fixed"] == data["errors"] == 0
        assert all(detail["action"] == "none" for detail in data["details"])
        assert stored(repair) is None
        assert stored(repair, 10) is None
    assert all(media.read_bytes() == b"unassigned synthetic media" for media in files)


def test_permission_error_is_not_missing_and_other_repairs_still_commit(
    repair, monkeypatch
):
    root = repair[3]
    denied = root / "denied.mp4"
    denied.write_bytes(b"protected")
    seed(repair, denied)
    good = root / "good.mp4"
    good.write_bytes(b"good")
    seed(repair, candidates=[(good, "completed")], stream_id=2)
    original_stat = Path.stat

    def permission_stat(path, *args, **kwargs):
        if path == denied:
            raise PermissionError("synthetic permission denial")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", permission_stat)
    for dry_run in [True, False]:
        response = request(repair, dry_run)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["checked"] == 2 and data["fixed"] == data["errors"] == 1
        denied_result = next(item for item in data["details"] if item["stream_id"] == 1)
        assert denied_result["action"] == "none"
        assert denied_result["error"] == "Check failed"
        assert stored(repair) == str(denied)
    assert stored(repair, 2) == str(good)
    assert denied.read_bytes() == b"protected"


def test_commit_failure_returns_500_and_rolls_back_every_path(repair):
    root = repair[3]
    media = root / "owned.mp4"
    media.write_bytes(b"unchanged")
    seed(repair, candidates=[(media, "completed")])
    session_class = repair[2].class_

    def fail_commit(_session):
        raise RuntimeError("synthetic commit failure")

    event.listen(session_class, "before_commit", fail_commit)
    try:
        response = request(repair)
    finally:
        event.remove(session_class, "before_commit", fail_commit)
    assert response.status_code == 500
    assert response.json() == {"detail": "Recording fix failed"}
    assert stored(repair) is None
    assert media.read_bytes() == b"unchanged"


@pytest.mark.parametrize(
    "mode,extra", [("jwt", {}), ("cookie", {"origin": "https://foreign.invalid"})]
)
def test_repair_retains_admin_and_csrf_boundaries(admin_stack, tmp_path, mode, extra):
    app, _, factory, _, _ = admin_stack
    media = tmp_path / "preserved.mp4"
    media.write_bytes(b"not touched")
    headers = credential_headers(
        admin_stack, mode, "nonadmin" if mode == "jwt" else "admin"
    )
    stack = (None, headers, factory, tmp_path)
    seed(stack, media)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/admin/recordings/fix-availability?dry_run=false",
            headers=headers | extra,
        )
        assert response.status_code == 403
        assert stored(stack) == str(media)
        assert media.read_bytes() == b"not touched"
    finally:
        client.close()
