"""Banner image worker/session/HTTP contracts use real local catalogues."""

from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Streamer
from app.services.images.banner_image_service import BannerImageService
from app.services.images.image_download_service import ImageDownloadService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_boundary

image_origin = test_image_http_boundary.image_origin


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["download", "sync", "cleanup"])
async def test_banner_catalogue_and_files_stay_in_their_owner_worker(
    tmp_path, image_origin, monkeypatch, operation
):
    base, _ = image_origin
    databases, services = [], []
    sql_threads, file_threads, checkouts = [], [], []
    loop_thread = get_ident()
    native_stat, native_unlink, native_mkdir = Path.stat, Path.unlink, Path.mkdir

    def mkdir(path, *args, **kwargs):
        if "/.media/banners" in str(path):
            file_threads.append(get_ident())
        return native_mkdir(path, *args, **kwargs)

    def stat(path, *args, **kwargs):
        if "/.media/banners" in str(path):
            file_threads.append(get_ident())
        return native_stat(path, *args, **kwargs)

    def unlink(path, *args, **kwargs):
        if "/.media/banners" in str(path):
            file_threads.append(get_ident())
        return native_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "unlink", unlink)
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
                        id=1,
                        twitch_id=f"tenant-{index}",
                        username=f"owner-{index}",
                        original_offline_image_url=base + "/image",
                    )
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: sql_threads.append(get_ident()),
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
                BannerImageService(
                    downloader, session_factory=database.sync_session_factory
                )
            )
        for index, service in enumerate(services):
            if operation == "cleanup":
                folder = service.download_service.images_base_dir / "banners"
                folder.mkdir(parents=True)
                live, orphan = folder / "banner_1.jpg", folder / "banner_99.png"
                live.write_bytes(b"live")
                orphan.write_bytes(b"orphan")
                file_threads.clear()
                assert await service.cleanup_unused_banner_images() == 1
                assert file_threads and loop_thread not in file_threads
                assert live.read_bytes() == b"live" and not orphan.exists()
                file_threads.clear()
            else:
                if operation == "sync":
                    assert await service.sync_all_banner_images() == {
                        "downloaded": 1,
                        "failed": 0,
                        "skipped": 0,
                        "total": 1,
                    }
                else:
                    assert (
                        await service.download_banner_image(1, base + "/image")
                        == "/data/images/banners/banner_1.jpg"
                    )
            assert sql_threads and loop_thread not in sql_threads
            if operation != "cleanup":
                assert file_threads and loop_thread not in file_threads
            assert all(count == 0 for observation in checkouts for count in observation)
            sql_threads.clear()
            file_threads.clear()
            with databases[index].sync_session_factory() as session:
                row = session.get(Streamer, 1)
                if operation != "cleanup":
                    assert row.offline_image_url == "/data/images/banners/banner_1.jpg"
                    assert row.original_offline_image_url == base + "/image"
            sql_threads.clear()
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for service in services:
            await service.download_service.close()
        for database in databases:
            await database.adispose()


def test_banner_directory_failure_does_not_use_a_foreign_fallback(
    tmp_path, monkeypatch
):
    service = BannerImageService(
        ImageDownloadService(
            settings=Settings(
                ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
            )
        )
    )
    attempted = []

    def denied(path, *args, **kwargs):
        attempted.append(path)
        raise PermissionError("fixture denied")

    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(OSError):
        service._ensure_banners_dir()
    assert attempted == [tmp_path / ".media/banners"]


@pytest.mark.asyncio
async def test_banner_disk_reload_skip_public_fallback_and_retry(
    tmp_path, image_origin, monkeypatch
):
    base, _ = image_origin
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'reload.db'}")
    downloader = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        )
    )
    service = BannerImageService(
        downloader, session_factory=database.sync_session_factory
    )
    folder = tmp_path / ".media/banners"
    folder.mkdir(parents=True)
    live = folder / "banner_1.jpg"
    live.write_bytes(b"previous image")
    (folder / "banner_invalid.png").write_bytes(b"unparsed")
    orphan = folder / "banner_99.png"
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(
                Streamer(
                    id=1,
                    twitch_id="fixture",
                    username="fixture",
                    original_offline_image_url=base + "/image",
                )
            )
            session.commit()
        stats = await run_in_thread_pool(service.get_banner_cache_stats)
        assert stats == {"cached_banners": 1, "failed_downloads": 0, "files_on_disk": 2}
        assert (
            await run_in_thread_pool(service.get_banner_image_url, 1)
            == "/data/images/banners/banner_1.jpg"
        )
        assert (
            await run_in_thread_pool(service.get_banner_image_url, 99, "original")
            == "original"
        )
        assert await service.sync_all_banner_images() == {
            "downloaded": 0,
            "failed": 0,
            "skipped": 1,
            "total": 1,
        }
        assert not await service.update_streamer_banner_image(1, base + "/denied")
        assert live.read_bytes() == b"previous image"
        assert await service.download_banner_image(1, "") is None
        assert await service.update_streamer_banner_image(1, base + "/image")
        assert live.read_bytes() == b"fixture-image-bytes"
        orphan.write_bytes(b"owned orphan")
        native_unlink = Path.unlink

        def deny(path, *args, **kwargs):
            if path == orphan:
                raise PermissionError("fixture denied")
            return native_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", deny)
        assert await service.cleanup_unused_banner_images() == 0
        assert orphan.read_bytes() == b"owned orphan"
        monkeypatch.setattr(Path, "unlink", native_unlink)
        assert await service.cleanup_unused_banner_images() == 1
        assert not orphan.exists() and live.exists()
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await downloader.close()
        await database.adispose()
