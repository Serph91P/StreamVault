"""Metadata input/cache/tool failures exercise the real session and child seams."""

import subprocess

import pytest
from PIL import Image

from app.models import Stream, StreamMetadata
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_metadata_media_server_contracts

metadata_catalog = test_metadata_media_server_contracts.metadata_catalog


@pytest.mark.asyncio
async def test_metadata_target_corrects_only_to_the_authoritative_recording(
    metadata_catalog,
):
    service, database, directory, _, _ = metadata_catalog
    result = await run_in_thread_pool(
        service._prepare_metadata_target, 1, str(directory.parent), "wrong-name"
    )
    assert (
        result is not None
        and result.directory == directory
        and result.filename == "original"
    )
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing-row", "missing-streamer", "session-failure"])
async def test_metadata_missing_catalogue_inputs_publish_nothing(
    metadata_catalog, monkeypatch, kind
):
    service, database, directory, _, _ = metadata_catalog
    identifier = 999
    if kind == "missing-streamer":
        with database.sync_session_factory() as db:
            db.add(Stream(id=999, streamer_id=777, title="no parent"))
            db.commit()
    if kind == "session-failure":

        def unavailable():
            raise OSError("synthetic unavailable catalogue")

        monkeypatch.setattr(service, "_session_factory", unavailable)
    assert (
        await run_in_thread_pool(
            service._prepare_metadata_target, identifier, str(directory), "missing"
        )
        is None
    )
    assert not (directory / "missing.nfo").exists()
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_native_cached_thumbnail_is_reused_and_remembered(metadata_catalog):
    service, database, directory, video, _ = metadata_catalog
    thumbnail = directory / "original_thumbnail.jpg"
    Image.new("RGB", (512, 512), "blue").save(thumbnail, "JPEG")
    assert thumbnail.stat().st_size > 1000
    original = thumbnail.read_bytes()
    with database.sync_session_factory() as db:
        db.query(StreamMetadata).filter(
            StreamMetadata.stream_id == 1
        ).first().thumbnail_path = None
        db.commit()
    assert await service.extract_thumbnail(str(video), 1) == str(thumbnail)
    assert thumbnail.read_bytes() == original
    with database.sync_session_factory() as db:
        assert db.query(StreamMetadata).filter(
            StreamMetadata.stream_id == 1
        ).first().thumbnail_path == str(thumbnail)
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["absent", "missing-ffprobe", "audio-only"])
async def test_thumbnail_failure_never_publishes_a_path(
    metadata_catalog, monkeypatch, kind
):
    service, database, directory, video, _ = metadata_catalog
    target = video
    if kind == "absent":
        target = directory / "absent.mp4"
    elif kind == "audio-only":
        target = directory / "audio.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440",
                "-t",
                "0.1",
                str(target),
            ],
            check=True,
        )
    original = target.read_bytes() if target.exists() else None
    with monkeypatch.context() as patch:
        if kind == "missing-ffprobe":
            patch.setenv("PATH", str(directory / "absent-tools"))
        assert await service.extract_thumbnail(str(target), 1) is None
    assert (target.read_bytes() if target.exists() else None) == original
    assert not target.with_name(target.stem + "_thumbnail.jpg").exists()
    with database.sync_session_factory() as db:
        assert db.query(StreamMetadata).filter(
            StreamMetadata.stream_id == 1
        ).first().thumbnail_path == str(directory / "source.jpg")
    assert database.sync_engine.pool.checkedout() == 0
