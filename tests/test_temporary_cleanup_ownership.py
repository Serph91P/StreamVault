"""#938: mounted admin cleanup must not unlink capture/recovery sources."""

from contextlib import closing
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests import test_admin_authorization as authorization

admin_stack = authorization.admin_stack
credential_headers = authorization.credential_headers


def expired(path: Path, content: bytes = b"synthetic temporary content") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    old = time.time() - 48 * 3600
    os.utime(path, (old, old))
    return path


def test_failed_unlink_reports_no_reclaimed_space_and_can_be_retried(
    admin_stack, monkeypatch
):
    from app.services.system import temporary_cleanup_service

    app, _settings, _factory, media, _queue = admin_stack
    target = expired(media.parent / "unowned.tmp")
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        preview = client.post(
            "/api/admin/maintenance/cleanup-temp", headers=headers
        ).json()
        payload = {
            "dry_run": False,
            "confirmed": True,
            "candidates": preview["candidates"],
        }

        def denied(*_args, **_kwargs):
            raise PermissionError("injected unlink denial")

        with monkeypatch.context() as failing:
            failing.setattr(temporary_cleanup_service.os, "unlink", denied)
            result = client.post(
                "/api/admin/maintenance/cleanup-temp", headers=headers, json=payload
            )
        assert result.status_code == 200
        assert result.json()["files_removed"] == 0
        assert result.json()["space_freed_mb"] == 0
        assert result.json()["errors"]
        assert target.exists() and media.exists()
        retry = client.post(
            "/api/admin/maintenance/cleanup-temp", headers=headers, json=payload
        )
        assert retry.json()["files_removed"] == 1
        assert not target.exists() and media.exists()


def test_cleanup_defaults_to_preview_and_requires_confirmation(admin_stack):
    app, _settings, _factory, media, _queue = admin_stack
    temporary = expired(media.parent / "unassociated" / "expired.tmp")
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        preview = client.post("/api/admin/maintenance/cleanup-temp", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["files_removed"] == 0
        assert preview.json()["dry_run"] is True
        assert temporary.exists() and media.exists()
        candidates = preview.json()["candidates"]
        assert [row["path"] for row in candidates] == ["unassociated/expired.tmp"]
        rejected = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={"dry_run": False},
        )
        assert rejected.status_code == 400
        assert temporary.exists() and media.exists()
        confirmed = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={"dry_run": False, "confirmed": True, "candidates": candidates},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["files_removed"] == 1
        assert not temporary.exists() and media.exists()


def test_cleanup_never_removes_unregistered_recoverable_media_or_new_temps(admin_stack):
    app, _settings, _factory, media, _queue = admin_stack
    protected = [
        expired(media.parent / name)
        for name in (
            "unprocessed.ts",
            "partial.part",
            "video.h264",
            "audio.aac",
            "segments/000.ts",
            "partial.mp4.tmp",
            "unfinished_segments/000.tmp",
        )
    ]
    recent = media.parent / "recent.tmp"
    recent.write_bytes(b"currently staged")
    with media.open("ab") as writer, closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        response = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={"dry_run": True},
        )
        assert response.status_code == 200
        assert response.json()["candidates"] == []
        assert response.json()["files_removed"] == 0
        assert os.fstat(writer.fileno()).st_nlink == 1
        assert all(path.exists() for path in protected + [media, recent])


def test_confirmation_does_not_delete_replaced_or_newly_discovered_candidates(
    admin_stack,
):
    app, _settings, _factory, media, _queue = admin_stack
    target = expired(media.parent / "old.tmp")
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        preview = client.post(
            "/api/admin/maintenance/cleanup-temp", headers=headers
        ).json()
        target.unlink()
        target.write_bytes(b"replacement must survive")
        added = expired(media.parent / "newly-discovered.tmp")
        response = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={
                "dry_run": False,
                "confirmed": True,
                "candidates": preview["candidates"],
            },
        )
        assert response.status_code == 200
        assert response.json()["files_removed"] == 0
        assert target.read_bytes() == b"replacement must survive"
        assert added.exists()


@pytest.mark.parametrize("status", ["recording", "processing", "failed", "completed"])
@pytest.mark.parametrize("alias", [False, True])
def test_catalog_media_and_its_partial_outputs_remain_protected(
    admin_stack, status, alias
):
    from app.models import Recording, Stream, Streamer

    app, _settings, factory, media, _queue = admin_stack
    source = expired(media.parent / "catalog" / "source.ts")
    partial = expired(source.with_suffix(".tmp"))
    genuine = expired(media.parent / "unowned" / "expired.tmp")
    reference = source
    if alias:
        link = media.parent / "catalog-alias"
        link.symlink_to(source.parent, target_is_directory=True)
        reference = link / source.name
    with factory() as db:
        streamer = Streamer(username="catalog", twitch_id="938")
        db.add(streamer)
        db.flush()
        stream = Stream(
            streamer_id=streamer.id,
            title="synthetic",
            started_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add(stream)
        db.flush()
        db.add(
            Recording(
                stream_id=stream.id,
                path=str(reference),
                status=status,
                start_time=stream.started_at,
            )
        )
        db.commit()
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        preview = client.post(
            "/api/admin/maintenance/cleanup-temp", headers=headers
        ).json()
        assert [item["path"] for item in preview["candidates"]] == [
            "unowned/expired.tmp"
        ]
        result = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={
                "dry_run": False,
                "confirmed": True,
                "candidates": preview["candidates"],
            },
        )
        assert result.json()["files_removed"] == 1
        assert source.exists() and partial.exists() and not genuine.exists()
        with factory() as db:
            assert db.query(Recording).one().status == status


@pytest.mark.parametrize("mapped", [True, False])
@pytest.mark.parametrize("stale_pid", [False, True])
def test_reserved_channel_protects_temp_outputs_before_recording_identity_exists(
    admin_stack,
    mapped,
    stale_pid,
):
    import asyncio
    from app.models import Streamer
    from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator

    app, _settings, factory, media, _queue = admin_stack
    pending = expired(media.parent / "reserved" / "pending.tmp")
    with factory() as db:
        if mapped:
            db.add(Streamer(username="reserved", twitch_id="938-reserved"))
        db.commit()
    coordinator = TwitchUpstreamCoordinator(factory, monotonic_clock=time.monotonic)
    asyncio.run(
        coordinator.reserve(
            channel_key="938-reserved", auth_key=None, purpose="RECORDING"
        )
    )
    if stale_pid:
        import subprocess
        import sys
        from app.models import TwitchUpstreamLease

        with subprocess.Popen(
            [sys.executable, "-c", "pass"], start_new_session=True
        ) as child:
            child.wait()
            with factory() as db:
                lease = db.query(TwitchUpstreamLease).one()
                lease.state = "ROTATING"
                lease.process_pid = child.pid
                db.commit()
    with closing(TestClient(app)) as client:
        preview = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=credential_headers(admin_stack, "jwt", "admin"),
        )
        assert preview.status_code == 200
        assert preview.json()["candidates"] == []
        assert pending.exists()


def test_symlink_escape_and_forged_confirmation_do_not_touch_external_file(
    admin_stack, tmp_path_factory
):
    app, _settings, _factory, media, _queue = admin_stack
    outside = expired(tmp_path_factory.mktemp("outside938") / "outside.tmp")
    escape = media.parent / "escape"
    escape.symlink_to(outside.parent, target_is_directory=True)
    info = outside.stat()
    forged = {
        "path": "escape/outside.tmp",
        "device": str(info.st_dev),
        "inode": str(info.st_ino),
        "size": str(info.st_size),
        "mtime_ns": str(info.st_mtime_ns),
    }
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        preview = client.post(
            "/api/admin/maintenance/cleanup-temp", headers=headers
        ).json()
        assert preview["candidates"] == []
        response = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={"dry_run": False, "confirmed": True, "candidates": [forged]},
        )
        assert response.status_code == 200
        assert response.json()["files_removed"] == 0
        assert response.json()["errors"]
        assert outside.read_bytes() == b"synthetic temporary content"


def test_browser_number_roundtrip_preserves_exact_confirmation_identity(admin_stack):
    app, _settings, _factory, media, _queue = admin_stack
    target = expired(media.parent / "nanosecond.tmp")
    os.utime(target, ns=(1700000000000000001, 1700000000000000001))
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        preview = client.post(
            "/api/admin/maintenance/cleanup-temp", headers=headers
        ).json()
        # ECMAScript JSON numbers are IEEE754 doubles; identity must not lose bits.
        echoed = json.loads(json.dumps(preview["candidates"]), parse_int=float)
        response = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=headers,
            json={"dry_run": False, "confirmed": True, "candidates": echoed},
        )
        assert response.json()["files_removed"] == 1
        assert not target.exists()


@pytest.mark.parametrize(
    "mode",
    ["jwt", "cookie", "legacy", "legacy-bearer", "api-key", "api-key-authorization"],
)
@pytest.mark.parametrize(
    "state", ["admin", "nonadmin", "disabled", "demoted", "anonymous"]
)
def test_confirmed_real_deletion_retains_current_admin_authorization(
    admin_stack, mode, state
):
    app, _settings, _factory, media, _queue = admin_stack
    target = expired(media.parent / "authorization.tmp")
    info = target.stat()
    candidate = {
        "path": target.name,
        "device": str(info.st_dev),
        "inode": str(info.st_ino),
        "size": str(info.st_size),
        "mtime_ns": str(info.st_mtime_ns),
    }
    with closing(TestClient(app)) as client:
        response = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=credential_headers(admin_stack, mode, state),
            json={"dry_run": False, "confirmed": True, "candidates": [candidate]},
        )
        if state == "admin":
            assert response.status_code == 200
            assert response.json()["files_removed"] == 1
            assert not target.exists()
        else:
            assert response.status_code in {401, 403}
            assert target.exists()
        assert media.exists()


def test_legacy_stream_catalog_protects_media_without_a_recording_row(admin_stack):
    from app.models import Stream, Streamer

    app, _settings, factory, media, _queue = admin_stack
    source = expired(media.parent / "legacy" / "source.ts")
    partial = expired(source.with_suffix(".tmp"))
    with factory() as db:
        streamer = Streamer(username="legacy", twitch_id="938-legacy")
        db.add(streamer)
        db.flush()
        db.add(
            Stream(
                streamer_id=streamer.id,
                title="legacy",
                started_at=datetime.now(timezone.utc),
                recording_path=str(source),
            )
        )
        db.commit()
    with closing(TestClient(app)) as client:
        response = client.post(
            "/api/admin/maintenance/cleanup-temp",
            headers=credential_headers(admin_stack, "jwt", "admin"),
        )
        assert response.status_code == 200
        assert response.json()["candidates"] == []
        assert partial.exists() and source.exists()
