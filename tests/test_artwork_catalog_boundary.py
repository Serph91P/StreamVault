"""Stream artwork uses owner-local scalar catalogues and worker-owned file work."""

import importlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Stream, StreamMetadata, Streamer
from app.services.images.image_download_service import ImageDownloadService
from app.services.images.stream_artwork_service import StreamArtworkService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_boundary

image_origin = test_image_http_boundary.image_origin


@pytest.fixture
async def artwork_owners(tmp_path, image_origin, monkeypatch):
    base, _ = image_origin
    services, databases, queries, files, checkouts = [], [], [], [], []
    native_mkdir, native_stat, native_unlink = Path.mkdir, Path.stat, Path.unlink

    def observed(native):
        def operation(path, *args, **kwargs):
            if "/.media/artwork" in str(path):
                files.append(get_ident())
            return native(path, *args, **kwargs)

        return operation

    monkeypatch.setattr(Path, "mkdir", observed(native_mkdir))
    monkeypatch.setattr(Path, "stat", observed(native_stat))
    monkeypatch.setattr(Path, "unlink", observed(native_unlink))
    try:
        for index in range(2):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / f'owner-{index}.db'}")
            databases.append(database)
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(
                    Streamer(
                        id=1, username=f"owner-{index}", twitch_id=f"owner-{index}"
                    )
                )
                session.flush()
                session.add(
                    Stream(
                        id=1,
                        streamer_id=1,
                        title=f"title-{index}",
                        started_at=datetime.now(timezone.utc),
                    )
                )
                session.flush()
                session.add(StreamMetadata(stream_id=1, thumbnail_url=base + "/image"))
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            downloader = ImageDownloadService(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(tmp_path / f"root-{index}"),
                    _env_file=None,
                )
            )
            native_session = downloader.get_session

            async def checked_session(native=native_session):
                checkouts.append(
                    [database.sync_engine.pool.checkedout() for database in databases]
                )
                return await native()

            monkeypatch.setattr(downloader, "get_session", checked_session)
            services.append(
                StreamArtworkService(
                    downloader, session_factory=database.sync_session_factory
                )
            )
        yield services, databases, queries, files, checkouts, base
    finally:
        for service in services:
            await service.close()
        for database in databases:
            await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["download", "update", "sync", "bulk", "unused", "old"]
)
async def test_artwork_catalogues_and_files_stay_in_their_worker_owner(
    artwork_owners, operation
):
    services, databases, queries, files, checkouts, base = artwork_owners
    loop_thread = get_ident()
    for index, service in enumerate(services):
        if operation in {"unused", "old"}:
            folder = service.download_service.images_base_dir / "artwork/streamer_1"
            folder.mkdir(parents=True)
            live, orphan = folder / "stream_1.jpg", folder / "stream_99.jpg"
            live.write_bytes(b"live")
            orphan.write_bytes(b"orphan")
            os.utime(orphan, (time.time() - 172800, time.time() - 172800))
            files.clear()
            if operation == "unused":
                assert await service.cleanup_unused_artwork() == 1
            else:
                assert await service.cleanup_old_artwork(days_old=1) == 1
            assert files and loop_thread not in files
            assert live.read_bytes() == b"live" and not orphan.exists()
            files.clear()
        else:
            if operation == "download":
                assert (
                    await service.download_stream_artwork(1, 1, base + "/image")
                    == "/data/images/artwork/streamer_1/stream_1.jpg"
                )
            elif operation == "update":
                assert await service.update_stream_artwork(1, base + "/image")
            elif operation == "sync":
                assert await service.sync_stream_artwork([1]) == {
                    "downloaded": 1,
                    "skipped": 0,
                    "failed": 0,
                }
            else:
                assert await service.bulk_download_artwork(
                    [
                        {
                            "stream_id": 1,
                            "streamer_id": 1,
                            "thumbnail_url": base + "/image",
                        }
                    ]
                ) == {"downloaded": 1, "failed": 0}
            assert files and loop_thread not in files
            assert checkouts and all(
                count == 0 for observation in checkouts for count in observation
            )
        if operation in {"update", "sync", "unused"}:
            assert queries and loop_thread not in queries
        queries.clear()
        files.clear()
        with databases[index].sync_session_factory() as session:
            source = (
                session.query(StreamMetadata).filter_by(stream_id=1).one().thumbnail_url
            )
            assert source == (
                "/data/images/artwork/streamer_1/stream_1.jpg"
                if operation in {"update", "sync"}
                else base + "/image"
            )
        queries.clear()
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup", ["old", "unused"])
async def test_artwork_cleanup_does_not_follow_directory_symlinks_outside_media(
    tmp_path, monkeypatch, cleanup
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'symlink.db'}")
    downloader = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        )
    )
    service = StreamArtworkService(downloader)
    monkeypatch.setattr(
        importlib.import_module("app.services.images.stream_artwork_service"),
        "SessionLocal",
        database.sync_session_factory,
    )
    root = tmp_path / ".media/artwork"
    root.mkdir(parents=True)
    outside = tmp_path / "outside-media"
    outside.mkdir()
    target = outside / "stream_99.jpg"
    target.write_bytes(b"foreign preserved")
    os.utime(target, (time.time() - 172800, time.time() - 172800))
    (root / "streamer_99").symlink_to(outside, target_is_directory=True)
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        result = (
            await service.cleanup_old_artwork(days_old=1)
            if cleanup == "old"
            else await service.cleanup_unused_artwork()
        )
        assert target.exists(), (
            "cleanup must not unlink a file outside the configured media root"
        )
        assert target.read_bytes() == b"foreign preserved"
        assert result == 0
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
async def test_artwork_metadata_creation_disk_cache_failure_and_retry(artwork_owners):
    services, databases, _, _, _, base = artwork_owners
    service, database = services[0], databases[0]
    with database.sync_session_factory() as session:
        session.query(StreamMetadata).delete()
        session.add(
            Stream(
                id=2,
                streamer_id=1,
                title="no metadata",
                started_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    assert await service.update_stream_artwork(1, base + "/image")
    cached = "/data/images/artwork/streamer_1/stream_1.jpg"
    assert await run_in_thread_pool(service.get_cached_stream_artwork, 1, 1) == cached
    assert await run_in_thread_pool(service.get_cached_stream_artwork, 99, 1) is None
    assert await run_in_thread_pool(service.get_artwork_cache_stats) == {
        "cached_artworks": 1,
        "streamers_with_artwork": 1,
        "failed_downloads": 0,
    }
    with database.sync_session_factory() as session:
        assert session.query(StreamMetadata).count() == 1
        metadata = session.query(StreamMetadata).filter_by(stream_id=1).one()
        assert metadata.thumbnail_url == cached
        metadata.thumbnail_url = "previous-catalogue-path"
        session.commit()
    assert await service.download_stream_artwork(1, 1, base + "/image") == cached
    assert not await service.update_stream_artwork(999, base + "/image")
    assert await service.download_stream_artwork(1, 1, "") is None
    assert await service.download_stream_artwork(2, 1, base + "/denied") is None
    assert await service.download_stream_artwork(2, 1, base + "/denied") is None

    def denied_commit(_session):
        raise RuntimeError("synthetic commit failure")

    session_type = database.sync_session_factory.class_
    event.listen(session_type, "before_commit", denied_commit)
    try:
        assert not await service.update_stream_artwork(1, base + "/image")
    finally:
        event.remove(session_type, "before_commit", denied_commit)
    with database.sync_session_factory() as session:
        assert (
            session.query(StreamMetadata).filter_by(stream_id=1).one().thumbnail_url
            == "previous-catalogue-path"
        )
    assert await service.update_stream_artwork(1, base + "/image")
    assert await service.sync_stream_artwork() == {
        "downloaded": 0,
        "skipped": 2,
        "failed": 0,
    }
    assert await service.bulk_download_artwork(
        [{}, {"stream_id": 2, "streamer_id": 1, "thumbnail_url": base + "/denied"}]
    ) == {"downloaded": 0, "failed": 1}
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_artwork_sync_counts_failed_publication_and_retries(artwork_owners):
    services, databases, _, _, _, _ = artwork_owners
    service, database = services[0], databases[0]

    def denied_commit(_session):
        raise RuntimeError("synthetic publication failure")

    session_type = database.sync_session_factory.class_
    event.listen(session_type, "before_commit", denied_commit)
    try:
        assert await service.sync_stream_artwork() == {
            "downloaded": 0,
            "skipped": 0,
            "failed": 1,
        }
    finally:
        event.remove(session_type, "before_commit", denied_commit)
    with database.sync_session_factory() as session:
        assert session.query(StreamMetadata).one().thumbnail_url.startswith("http")
    assert await service.sync_stream_artwork() == {
        "downloaded": 1,
        "skipped": 0,
        "failed": 0,
    }
    with database.sync_session_factory() as session:
        assert (
            session.query(StreamMetadata).one().thumbnail_url
            == "/data/images/artwork/streamer_1/stream_1.jpg"
        )


@pytest.mark.asyncio
async def test_artwork_old_cleanup_keeps_failed_unlink_and_retries_empty_directory(
    artwork_owners, monkeypatch
):
    services, _, _, _, _, _ = artwork_owners
    service = services[0]
    folder = service.download_service.images_base_dir / "artwork/streamer_99"
    folder.mkdir(parents=True)
    target = folder / "stream_99.jpg"
    target.write_bytes(b"retry source")
    os.utime(target, (time.time() - 172800, time.time() - 172800))
    native_unlink = Path.unlink

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError("fixture denied")
        return native_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    assert await service.cleanup_old_artwork(days_old=1) == 0
    assert target.read_bytes() == b"retry source"
    monkeypatch.setattr(Path, "unlink", native_unlink)
    assert await service.cleanup_old_artwork(days_old=1) == 1
    assert not target.exists() and not folder.exists()
