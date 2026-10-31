"""Legacy image replacement must never publish a partial copy or lose a retry."""

import errno
import io
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.models import Streamer
from app.services.migration import image_migration_service as migration


def jpeg(color):
    output = io.BytesIO()
    Image.new("RGB", (3, 3), color).save(output, format="JPEG")
    return output.getvalue()


OLD_IMAGE = jpeg("red")
NEW_IMAGE = jpeg("blue")


@pytest.fixture
def legacy_tree(tmp_path):
    service = migration.ImageMigrationService()
    service.recordings_dir = tmp_path / "recordings"
    service.old_images_dir = service.recordings_dir / ".images"
    service.old_artwork_dir = service.recordings_dir / ".artwork"
    streamer = Streamer(id=123, username="synthetic")
    (service.recordings_dir / "synthetic").mkdir(parents=True)
    source = service.old_artwork_dir / "synthetic" / "poster.jpg"
    target = service.recordings_dir / ".media/artwork/synthetic/poster.jpg"
    source.parent.mkdir(parents=True)
    source.write_bytes(NEW_IMAGE)
    target.parent.mkdir(parents=True)
    target.write_bytes(OLD_IMAGE)
    os.utime(target, (100, 100))
    os.utime(source, (200, 200))
    return service, streamer, source, target


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_target", [True, False])
@pytest.mark.parametrize("failure", ["copy", "partial-copy", "short-copy", "replace"])
async def test_failed_replacement_preserves_images_and_retries(
    legacy_tree, monkeypatch, existing_target, failure
):
    service, streamer, source, target = legacy_tree
    if not existing_target:
        target.unlink()

    def cross_device(*args, **kwargs):
        # Exercise shutil.move's copy fallback on the unfixed implementation.
        raise OSError(errno.EXDEV, "synthetic cross-device move")

    def fail_copy(src, dst, *args, **kwargs):
        if failure in {"partial-copy", "short-copy"}:
            Path(dst).write_bytes(NEW_IMAGE[:20])
            if failure == "short-copy":
                return str(dst)
            raise OSError("synthetic interrupted write")
        raise PermissionError("synthetic copy denied")

    def fail_replace(*args, **kwargs):
        raise PermissionError("synthetic replace denied")

    with monkeypatch.context() as faults:
        faults.setattr(os, "rename", cross_device)
        if failure == "replace":
            faults.setattr(os, "replace", fail_replace)
        else:
            faults.setattr(migration.shutil, "copyfile", fail_copy)
        result = await service.migrate_streamer_images(streamer)

    assert source.read_bytes() == NEW_IMAGE
    if existing_target:
        assert target.read_bytes() == OLD_IMAGE
        Image.open(target).verify()
    else:
        assert not target.exists()
    assert result == {"images_moved": 0, "duplicates_found": 0, "errors": 1}
    assert sorted(p.name for p in target.parent.iterdir()) == (
        ["poster.jpg"] if existing_target else []
    )
    # The failed source also prevents cleanup of the legacy tree.
    await service.cleanup_old_directories()
    assert source.read_bytes() == NEW_IMAGE

    retry = await service.migrate_streamer_images(streamer)
    assert retry == {"images_moved": 1, "duplicates_found": 0, "errors": 0}
    assert target.read_bytes() == NEW_IMAGE
    Image.open(target).verify()
    assert not source.exists()
    assert await service.migrate_streamer_images(streamer) == {
        "images_moved": 0,
        "duplicates_found": 0,
        "errors": 0,
    }
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.asyncio
async def test_target_changes_only_after_complete_copy(legacy_tree, monkeypatch):
    service, streamer, source, target = legacy_tree
    original_copyfile = migration.shutil.copyfile
    observed = []

    def observe_copy(src, dst, *args, **kwargs):
        assert target.read_bytes() == OLD_IMAGE
        result = original_copyfile(src, dst, *args, **kwargs)
        assert Path(dst).read_bytes() == NEW_IMAGE
        assert source.read_bytes() == NEW_IMAGE
        assert target.read_bytes() == OLD_IMAGE
        observed.append(Path(dst))
        return result

    monkeypatch.setattr(migration.shutil, "copyfile", observe_copy)
    result = await service.migrate_streamer_images(streamer)
    assert result == {"images_moved": 1, "duplicates_found": 0, "errors": 0}
    assert len(observed) == 1
    assert observed[0].is_relative_to(target.parent)
    assert target.read_bytes() == NEW_IMAGE
    assert not source.exists()
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content", [OLD_IMAGE, NEW_IMAGE], ids=["identical", "older-source"]
)
async def test_identical_or_newer_target_is_kept(legacy_tree, content):
    service, streamer, source, target = legacy_tree
    source.write_bytes(content)
    os.utime(source, (50, 50))
    result = await service.migrate_streamer_images(streamer)
    assert result == {"images_moved": 0, "duplicates_found": 1, "errors": 0}
    assert target.read_bytes() == OLD_IMAGE
    assert not source.exists()


@pytest.mark.asyncio
async def test_profile_and_sanitized_name_stay_in_recordings_tree(legacy_tree):
    service, streamer, source, target = legacy_tree
    streamer.username = "../../synthetic/channel"
    (service.recordings_dir / "_.._synthetic_channel").mkdir()
    source.unlink()
    profile = service.old_images_dir / "profiles/streamer_123.jpg"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(NEW_IMAGE)
    result = await service.migrate_streamer_images(streamer)
    expected = (
        service.recordings_dir / ".media/artwork/_.._synthetic_channel/poster.jpg"
    )
    assert result == {"images_moved": 1, "duplicates_found": 0, "errors": 0}
    assert expected.read_bytes() == NEW_IMAGE
    assert expected.resolve().is_relative_to(service.recordings_dir.resolve())
    assert not profile.exists()
    assert target.read_bytes() == OLD_IMAGE


@pytest.mark.asyncio
async def test_batch_reports_failed_items_without_counting_streamer_as_success(
    legacy_tree, monkeypatch, caplog
):
    from app.utils import async_db_utils

    service, streamer, source, target = legacy_tree

    async def streamers():
        return [streamer]

    def denied(*args, **kwargs):
        raise PermissionError("synthetic copy denied")

    monkeypatch.setattr(async_db_utils, "get_all_streamers", streamers)
    monkeypatch.setattr(migration.shutil, "copyfile", denied)
    monkeypatch.setattr(os, "rename", denied)
    stats = await service.migrate_all_images()
    assert stats["errors"] == 1
    assert stats["streamers_migrated"] == 0
    assert stats["images_moved"] == 0
    assert stats["directories_cleaned"] == 0
    assert target.read_bytes() == OLD_IMAGE
    assert source.read_bytes() == NEW_IMAGE
    assert "Migration completed with errors" in caplog.text


def test_http_migration_reports_failure_and_successful_retry(legacy_tree, monkeypatch):
    from app.routes import migration as routes
    from app.utils import async_db_utils

    service, streamer, source, target = legacy_tree

    async def streamers():
        return [streamer]

    def denied(*args, **kwargs):
        raise PermissionError("synthetic copy denied")

    monkeypatch.setattr(async_db_utils, "get_all_streamers", streamers)
    monkeypatch.setattr(routes, "image_migration_service", service)
    application = FastAPI()
    application.include_router(routes.router)
    with TestClient(application) as client:
        with monkeypatch.context() as faults:
            faults.setattr(migration.shutil, "copyfile", denied)
            faults.setattr(os, "rename", denied)
            response = client.post("/api/migration/images")
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert response.json()["stats"]["errors"] == 1
        assert "errors" in response.json()["message"]
        assert target.read_bytes() == OLD_IMAGE
        assert source.read_bytes() == NEW_IMAGE
        retry = client.post("/api/migration/images").json()
        assert retry["success"] is True
        assert retry["stats"]["errors"] == 0
        assert retry["stats"]["images_moved"] == 1
        assert target.read_bytes() == NEW_IMAGE
        assert not source.exists()
        assert (
            client.get("/api/migration/images/status").json()["migration_needed"]
            is False
        )
