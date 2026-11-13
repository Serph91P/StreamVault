"""Profile images keep catalogue/session and filesystem work with their owner."""

import importlib
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Streamer
from app.services.images.image_download_service import ImageDownloadService
from app.services.images.profile_image_service import ProfileImageService
from tests import test_image_http_boundary

image_origin = test_image_http_boundary.image_origin


def test_profile_directory_failure_does_not_touch_another_root(tmp_path, monkeypatch):
    downloader = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        )
    )
    service = ProfileImageService(downloader)
    attempts = []

    def mkdir(path, *args, **kwargs):
        attempts.append(path)
        raise PermissionError("fixture denied")

    monkeypatch.setattr(Path, "mkdir", mkdir)
    with pytest.raises((OSError, RuntimeError)):
        service._ensure_profiles_dir()
    assert attempts == [tmp_path / ".media" / "profiles"]
    assert service.profiles_dir in (None, tmp_path / ".media" / "profiles")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["sync", "update"])
async def test_profile_catalogues_are_injected_and_never_held_over_http(
    tmp_path, image_origin, monkeypatch, operation
):
    base, _ = image_origin
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    services, queries, checkouts = [], [], []
    loop_thread = get_ident()
    fs_threads = []
    native_stat, native_replace = Path.stat, Path.replace

    def track(path):
        if str(path).startswith(str(tmp_path / "owner-")):
            fs_threads.append(get_ident())

    def stat(path, *args, **kwargs):
        track(path)
        return native_stat(path, *args, **kwargs)

    def replace(path, *args, **kwargs):
        track(path)
        return native_replace(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "replace", replace)
    try:
        for index, database in enumerate(databases):
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(
                    Streamer(
                        id=1,
                        username=f"owner-{index}",
                        twitch_id=f"tenant-{index}",
                        profile_image_url=base + "/image",
                    )
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            downloader = ImageDownloadService(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(tmp_path / f"owner-{index}"),
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
                ProfileImageService(
                    downloader, session_factory=database.sync_session_factory
                )
            )
        for index, service in enumerate(services):
            if operation == "sync":
                result = await service.sync_all_profile_images()
                assert result == {"downloaded": 1, "skipped": 0, "failed": 0}
            else:
                assert await service.update_streamer_profile_image(1, base + "/image")
            assert queries and loop_thread not in queries
            assert fs_threads and loop_thread not in fs_threads
            assert checkouts and all(
                count == 0 for observation in checkouts for count in observation
            )
            before = len(queries)
            with databases[index].sync_session_factory() as session:
                assert session.get(Streamer, 1).profile_image_url.endswith(
                    f"profile_avatar_tenant-{index}.jpg"
                )
            del queries[before:]
            assert all(
                database.sync_engine.pool.checkedout() == 0 for database in databases
            )
    finally:
        for service in services:
            await service.close()
        for database in databases:
            await database.adispose()


@pytest.mark.asyncio
async def test_profile_cleanup_keeps_live_twitch_names_and_deletes_only_orphans(
    tmp_path, monkeypatch
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'cleanup.db'}")
    downloader = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        )
    )
    service = ProfileImageService(downloader)
    module = importlib.import_module("app.services.images.profile_image_service")
    monkeypatch.setattr(module, "SessionLocal", database.sync_session_factory)
    folder = downloader.images_base_dir / "profiles"
    folder.mkdir(parents=True)
    paths = {
        name: folder / name
        for name in (
            "profile_avatar_123456.jpg",
            "streamer_1.jpg",
            "profile_avatar_orphan.jpg",
            "unrelated.jpg",
        )
    }
    unlink_threads = []
    native_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path.is_relative_to(folder):
            unlink_threads.append(get_ident())
        return native_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    for path in paths.values():
        path.write_bytes(b"owned fixture")
    service._profile_cache["1"] = (
        "/recordings/.media/profiles/profile_avatar_123456.jpg"
    )
    service._profile_cache["99"] = (
        "/recordings/.media/profiles/profile_avatar_orphan.jpg"
    )
    service._profile_sources["99"] = "https://fixture.invalid/old-profile"
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="fixture", twitch_id="123456"))
            session.commit()
        assert await service.cleanup_unused_profile_images() == 1
        assert paths["profile_avatar_123456.jpg"].read_bytes() == b"owned fixture"
        assert paths["streamer_1.jpg"].exists() and paths["unrelated.jpg"].exists()
        assert not paths["profile_avatar_orphan.jpg"].exists()
        assert unlink_threads and get_ident() not in unlink_threads
        assert (
            "99" not in service._profile_cache and "99" not in service._profile_sources
        )
        assert service._profile_cache["1"].endswith("profile_avatar_123456.jpg")
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
async def test_concurrent_profile_requests_initialize_shared_cache_once(
    tmp_path, image_origin, monkeypatch
):
    import asyncio
    from threading import Event

    base, _ = image_origin
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'concurrent.db'}")
    service = ProfileImageService(
        ImageDownloadService(
            settings=Settings(
                ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
            )
        ),
        session_factory=database.sync_session_factory,
    )
    with database.sync_engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    with database.sync_session_factory() as session:
        session.add(Streamer(id=1, username="fixture", twitch_id="fixture"))
        session.commit()
    loop = asyncio.get_running_loop()
    entered, second_entered = asyncio.Event(), asyncio.Event()
    release = Event()
    cache_queries = []

    def hold_initial_read(_connection, _cursor, statement, *_args):
        if "SELECT 1 FROM streamers" in statement:
            cache_queries.append(statement)
            if len(cache_queries) == 1:
                loop.call_soon_threadsafe(entered.set)
                release.wait(5)

    event.listen(database.sync_engine, "before_cursor_execute", hold_initial_read)
    native_cache = service._ensure_cache_loaded
    arrivals = []

    def cache():
        arrivals.append(1)
        if len(arrivals) == 2:
            loop.call_soon_threadsafe(second_entered.set)
        return native_cache()

    monkeypatch.setattr(service, "_ensure_cache_loaded", cache)
    operations = []
    try:
        operations.append(
            asyncio.create_task(service.download_profile_image(1, base + "/image"))
        )
        await asyncio.wait_for(entered.wait(), 5)
        operations.append(
            asyncio.create_task(service.download_profile_image(1, base + "/image"))
        )
        await asyncio.wait_for(second_entered.wait(), 5)
        await asyncio.sleep(0.05)
        assert len(cache_queries) == 1
        release.set()
        assert all(await asyncio.gather(*operations))
    finally:
        release.set()
        await asyncio.gather(*operations, return_exceptions=True)
        await service.close()
        await database.adispose()
