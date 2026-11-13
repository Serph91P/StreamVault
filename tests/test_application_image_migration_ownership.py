"""Actual authenticated migration requests stay inside their factory catalogue."""

from pathlib import Path
from threading import get_ident

import pytest

from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["status", "migrate"])
async def test_migration_http_uses_only_its_own_root_catalogue_and_worker(
    action, image_applications, monkeypatch
):
    apps, databases, clients, queries = image_applications
    sources, targets = [], []
    for index, app in enumerate(apps):
        root = Path(app.state.settings.RECORDING_DIRECTORY)
        (root / f"owner-{index}").mkdir()
        source = root / f".artwork/owner-{index}/poster.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(f"owner-{index}".encode())
        sources.append(source)
        targets.append(root / f".media/artwork/owner-{index}/poster.jpg")
    observed = []
    native_exists = Path.exists

    def exists(path, *args, **kwargs):
        if path.name in (".images", ".artwork"):
            observed.append(get_ident())
        return native_exists(path, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", exists)
    for index, client in enumerate(clients):
        observed.clear()
        queries.clear()
        root = Path(apps[index].state.settings.RECORDING_DIRECTORY)
        if action == "status":
            response = await client.get("/api/migration/images/status")
            assert response.status_code == 200, response.text
            assert response.json() == {
                "migration_needed": True,
                "old_images_dir_exists": False,
                "old_artwork_dir_exists": True,
                "recordings_dir": str(root),
            }
        else:
            response = await client.post("/api/migration/images")
            assert response.status_code == 200, response.text
            assert response.json()["success"] is True
            assert response.json()["stats"] == {
                "streamers_migrated": 1,
                "images_moved": 1,
                "duplicates_found": 0,
                "errors": 0,
                "directories_cleaned": 1,
            }
            assert not sources[index].exists()
            assert targets[index].read_bytes() == f"owner-{index}".encode()
            catalogue_threads = [
                thread for thread, sql in queries if "FROM streamers" in sql
            ]
            assert catalogue_threads and get_ident() not in catalogue_threads
            assert all(
                database.sync_engine.pool.checkedout() == 0 for database in databases
            )
            if index == 0:
                assert sources[1].read_bytes() == b"owner-1"
                assert not targets[1].exists()
        assert observed and get_ident() not in observed
