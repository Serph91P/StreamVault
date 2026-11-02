"""Legacy migration uses closed owner snapshots and safe worker-owned paths."""

from pathlib import Path
from threading import get_ident
import os

import pytest

from app.config.settings import Settings
from app.services.migration.image_migration_service import ImageMigrationService
from tests import test_image_sync_ownership
from tests import test_image_migration_safe_replace

sync_owners = test_image_sync_ownership.sync_owners
artwork_owners = test_image_sync_ownership.artwork_owners
image_origin = test_image_sync_ownership.image_origin
OLD_IMAGE = test_image_migration_safe_replace.OLD_IMAGE
NEW_IMAGE = test_image_migration_safe_replace.NEW_IMAGE


@pytest.mark.asyncio
async def test_migration_uses_only_its_closed_catalogue_and_worker_file_scope(
    sync_owners, monkeypatch
):
    _, facades, databases, queries, _ = sync_owners
    services, pairs = [], []
    for index, (facade, database) in enumerate(zip(facades, databases, strict=True)):
        root = facade.recordings_dir
        (root / f"owner-{index}").mkdir(parents=True)
        source = root / f".artwork/owner-{index}/poster.jpg"
        target = root / f".media/artwork/owner-{index}/poster.jpg"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(NEW_IMAGE)
        target.write_bytes(OLD_IMAGE)
        os.utime(target, (100, 100))
        os.utime(source, (200, 200))
        pairs.append((source, target))
        services.append(
            ImageMigrationService(
                settings=Settings(
                    ENVIRONMENT="test", RECORDING_DIRECTORY=str(root), _env_file=None
                ),
                session_factory=database.sync_session_factory,
            )
        )
    observed = []
    native_stat = Path.stat

    def stat(path, *args, **kwargs):
        if "/.artwork/" in str(path) or "/.media/artwork/" in str(path):
            observed.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    queries.clear()
    for index, service in enumerate(services):
        stats = await service.migrate_all_images()
        assert stats["streamers_migrated"] == stats["images_moved"] == 1
        assert stats["errors"] == 0
        assert queries and get_ident() not in queries
        assert observed and get_ident() not in observed
        queries.clear()
        observed.clear()
        source, target = pairs[index]
        assert not source.exists() and target.read_bytes() == NEW_IMAGE
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        if index == 0:
            assert pairs[1][0].read_bytes() == NEW_IMAGE
            assert pairs[1][1].read_bytes() == OLD_IMAGE
        observed.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("link_side", ["source", "target"])
async def test_migration_never_follows_foreign_directory_links(
    legacy_tree, tmp_path, link_side
):
    service, streamer, source, target = legacy_tree
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    sentinel = foreign / "poster.jpg"
    sentinel.write_bytes(OLD_IMAGE if link_side == "target" else NEW_IMAGE)
    if link_side == "source":
        source.unlink()
        source.parent.rmdir()
        source.parent.symlink_to(foreign, target_is_directory=True)
    else:
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(foreign, target_is_directory=True)
        os.utime(sentinel, (100, 100))
    result = await service.migrate_streamer_images(streamer)
    assert sentinel.read_bytes() == (OLD_IMAGE if link_side == "target" else NEW_IMAGE)
    assert source.read_bytes() == NEW_IMAGE
    assert result["images_moved"] == 0
    assert result["errors"] == 1


legacy_tree = test_image_migration_safe_replace.legacy_tree


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [False, True])
async def test_migration_cancellation_drains_real_copy_and_owned_tasks(
    legacy_tree, monkeypatch, batch
):
    import asyncio
    from threading import Event
    from app.services.migration import image_migration_service as migration

    service, streamer, source, target = legacy_tree
    entered, release = Event(), Event()
    native_copy = migration.shutil.copyfile

    def held_copy(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return native_copy(*args, **kwargs)

    monkeypatch.setattr(migration.shutil, "copyfile", held_copy)
    monkeypatch.setattr(service, "_streamers", lambda: [streamer])
    task = asyncio.create_task(
        service.migrate_all_images()
        if batch
        else service.migrate_streamer_images(streamer)
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        assert target.read_bytes() == OLD_IMAGE
        assert source.read_bytes() == NEW_IMAGE
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert target.read_bytes() == NEW_IMAGE
    assert not source.exists()
    assert list(target.parent.iterdir()) == [target]
    assert not [
        candidate
        for candidate in asyncio.all_tasks()
        if candidate.get_name().startswith("streamvault:image-migration:")
    ]
