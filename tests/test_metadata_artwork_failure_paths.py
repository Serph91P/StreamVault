"""Actual cached artwork/NFO publication and best-effort filesystem failures."""

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest

from app.models import Stream, Streamer, StreamMetadata
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_metadata_media_server_contracts

metadata_catalog = test_metadata_media_server_contracts.metadata_catalog


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["none", "copy-denied", "season-copy-denied"])
async def test_nfo_copies_central_artwork_without_network(
    metadata_catalog, monkeypatch, failure
):
    service, database, directory, _, _ = metadata_catalog
    root = directory.parent.parent
    central = root / ".media" / "artwork" / "alice"
    central.mkdir(parents=True)
    for name in ("poster.jpg", "fanart.jpg", "banner.jpg"):
        (central / name).write_bytes(name.encode())
    native = shutil.copy2

    def copy(source, destination, *args, **kwargs):
        target = Path(destination)
        if (failure == "copy-denied" and target.parent == directory.parent) or (
            failure == "season-copy-denied" and target.parent == directory
        ):
            raise PermissionError("synthetic cached artwork copy denial")
        return native(source, destination, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", copy)

    def write():
        with database.sync_session_factory() as db:
            streamer = db.get(Streamer, 1)
            streamer.profile_image_url = "https://uncontacted.invalid/avatar.jpg"
            streamer.description = "Channel biography"
            stream = db.get(Stream, 1)
            return service.generate_nfo_file(
                db,
                stream,
                streamer,
                directory,
                "original",
                db.query(StreamMetadata).first(),
            )

    assert await run_in_thread_pool(write)
    assert (
        ET.parse(directory.parent / "tvshow.nfo").getroot().findtext("plot")
        == "Channel biography"
    )
    assert ET.parse(directory / "original.nfo").getroot().tag == "episodedetails"
    assert (
        ET.parse(directory / "season.nfo").getroot().findtext("seasonnumber")
        == "202611"
    )
    if failure != "copy-denied":
        assert (directory.parent / "poster.jpg").read_bytes() == b"poster.jpg"
    if failure == "none":
        assert (directory / "poster.jpg").read_bytes() == b"poster.jpg"
        actor = directory.parent / ".Actors" / "alice" / "folder.jpg"
        assert actor.read_bytes() == b"poster.jpg"
    assert all(
        (central / name).read_bytes() == name.encode()
        for name in ("poster.jpg", "fanart.jpg", "banner.jpg")
    )
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_nfo_denied_output_is_false_and_does_not_replace_source(
    metadata_catalog, monkeypatch
):
    service, database, directory, video, _ = metadata_catalog
    original = video.with_suffix(".nfo").read_bytes()
    native = ET.ElementTree.write

    def denied(tree, file_or_filename, *args, **kwargs):
        if Path(file_or_filename) == video.with_suffix(".nfo"):
            raise PermissionError("synthetic NFO publication refusal")
        return native(tree, file_or_filename, *args, **kwargs)

    monkeypatch.setattr(ET.ElementTree, "write", denied)

    def write():
        with database.sync_session_factory() as db:
            return service.generate_nfo_file(
                db,
                db.get(Stream, 1),
                db.get(Streamer, 1),
                directory,
                "original",
                db.query(StreamMetadata).first(),
            )

    assert await run_in_thread_pool(write) is False
    assert video.with_suffix(".nfo").read_bytes() == original
    assert video.read_bytes() == b"synthetic sidecar target, not a decoding fixture"


async def test_relative_artwork_and_public_containment_fallbacks(
    metadata_catalog, monkeypatch
):
    service, _, directory, _, _ = metadata_catalog
    root = directory.parent.parent
    assert service.find_recordings_root(directory) is None
    assert (
        service._relative_artwork_path(directory, "alice", "poster.jpg")
        == ".media/artwork/alice/poster.jpg"
    )
    (root / ".media").mkdir()
    assert service.find_recordings_root(directory) == root
    assert service.is_within(directory, root)
    assert not service.is_within(root.parent, root)
    relative = service._relative_artwork_path(directory, "alice", "poster.jpg")
    assert (directory / relative).resolve() == root / ".media/artwork/alice/poster.jpg"
    import app.services.media.metadata_service as module

    def bad_relative(*_args, **_kwargs):
        raise ValueError("synthetic incompatible path volumes")

    monkeypatch.setattr(module.os.path, "relpath", bad_relative)
    assert (
        service._relative_artwork_path(directory, "alice", "poster.jpg")
        == ".media/artwork/alice/poster.jpg"
    )


@pytest.mark.asyncio
async def test_missing_central_artwork_does_not_create_fake_local_files(
    metadata_catalog,
):
    service, _, directory, _, _ = metadata_catalog
    root = directory.parent.parent
    (root / ".media").mkdir()
    await run_in_thread_pool(
        service._ensure_local_artwork, directory.parent, directory, "alice"
    )
    assert not (directory.parent / "poster.jpg").exists()
    assert not (directory / "poster.jpg").exists()
