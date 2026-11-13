"""Real category catalogues and loopback HTTP must not borrow the event-loop Session."""

from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Category
from app.services.images.category_image_service import CategoryImageService
from app.services.images.image_download_service import ImageDownloadService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_boundary

image_origin = test_image_http_boundary.image_origin


@pytest.fixture
async def category_owners(tmp_path, image_origin, monkeypatch):
    base, _ = image_origin
    databases, services = [], []
    queries, files, checkouts = [], [], []
    native_mkdir, native_stat, native_unlink = Path.mkdir, Path.stat, Path.unlink

    def observed(operation):
        def call(path, *args, **kwargs):
            if "/.media/categories" in str(path):
                files.append(get_ident())
            return operation(path, *args, **kwargs)

        return call

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
                    Category(
                        name="Just Chatting",
                        twitch_id="fixture",
                        box_art_url=base + "/image",
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
                CategoryImageService(
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
@pytest.mark.parametrize("operation", ["download", "update", "sync", "bulk"])
async def test_category_requests_use_closed_owner_snapshots_and_offloop_files(
    category_owners, operation
):
    services, databases, queries, files, checkouts, base = category_owners
    loop_thread = get_ident()
    for index, service in enumerate(services):
        if operation == "download":
            assert (
                await service.download_category_image("Just Chatting")
                == "/api/media/categories/just_chatting.jpg"
            )
        elif operation == "update":
            assert await service.update_category_image("Just Chatting", base + "/image")
        elif operation == "sync":
            assert await service.sync_all_category_images() == {
                "downloaded": 1,
                "skipped": 0,
                "failed": 0,
            }
        else:
            assert await service.bulk_sync_categories(
                [{"id": "new", "name": "New Game", "box_art_url": base + "/image"}]
            ) == {"updated": 1, "downloaded": 1, "failed": 0}
        assert queries and loop_thread not in queries
        assert files and loop_thread not in files
        assert checkouts and all(
            count == 0 for observation in checkouts for count in observation
        )
        queries.clear()
        files.clear()
        with databases[index].sync_session_factory() as session:
            if operation == "bulk":
                row = session.query(Category).filter_by(name="New Game").one()
                assert row.box_art_url == "/api/media/categories/new_game.jpg"
            else:
                row = session.query(Category).filter_by(name="Just Chatting").one()
                assert row.box_art_url == (
                    base + "/image"
                    if operation == "download"
                    else "/api/media/categories/just_chatting.jpg"
                )
        queries.clear()
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_category_cleanup_uses_authoritative_filenames_not_lossy_name_guessing(
    category_owners,
):
    services, databases, queries, files, _, _ = category_owners
    loop_thread = get_ident()
    for service in services:
        folder = service.download_service.images_base_dir / "categories"
        folder.mkdir(parents=True)
        live, orphan = folder / "just_chatting.jpg", folder / "old_game.jpg"
        live.write_bytes(b"live")
        orphan.write_bytes(b"orphan")
        files.clear()
        assert await service.cleanup_unused_category_images() == 1
        assert queries and loop_thread not in queries
        assert files and loop_thread not in files
        queries.clear()
        files.clear()
        assert live.read_bytes() == b"live" and not orphan.exists()
        files.clear()
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


def test_category_directory_failure_never_uses_shared_temp_storage(
    tmp_path, monkeypatch
):
    service = CategoryImageService(
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
        service._ensure_categories_dir()
    assert attempted == [tmp_path / ".media/categories"]


@pytest.mark.asyncio
async def test_category_background_lookup_is_awaitable_and_owns_its_tasks(
    category_owners,
):
    import asyncio

    services, databases, queries, files, checkouts, base = category_owners
    loop_thread = get_ident()
    for service in services:
        assert (
            await service.get_cached_category_image_with_download("Just Chatting")
            == base + "/image"
        )
        await asyncio.gather(*tuple(service._background_tasks))
        assert queries and loop_thread not in queries
        assert files and loop_thread not in files
        assert all(count == 0 for observation in checkouts for count in observation)
        queries.clear()
        files.clear()
        assert (
            await run_in_thread_pool(service.get_cached_category_image, "Just Chatting")
            == "/api/media/categories/just_chatting.jpg"
        )
        assert (await run_in_thread_pool(service.get_category_cache_stats))[
            "cached_categories"
        ] >= 1
        queries.clear()
        files.clear()
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_category_shutdown_cancels_only_owned_downloads_and_rejects_late_work(
    category_owners,
):
    import asyncio
    from aiohttp import web

    services, databases, _, _, _, _ = category_owners
    entered, release = asyncio.Event(), asyncio.Event()
    arrivals = []

    async def held(request):
        arrivals.append(request.path)
        if len(arrivals) == 2:
            entered.set()
        await release.wait()
        return web.Response(body=b"fixture-image", content_type="image/jpeg")

    origin = web.Application()
    origin.router.add_get("/{owner}", held)
    runner = web.AppRunner(origin)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    closing = None
    try:
        for index, (service, database) in enumerate(zip(services, databases)):
            url = f"http://127.0.0.1:{runner.addresses[0][1]}/{index}"
            with database.sync_session_factory() as session:
                session.query(Category).update({"box_art_url": url})
                session.commit()
            assert (
                await service.get_cached_category_image_with_download("Just Chatting")
                == url
            )
        await asyncio.wait_for(entered.wait(), 5)
        peer_tasks = tuple(services[1]._background_tasks)
        closing = asyncio.create_task(services[0].close())
        await asyncio.wait_for(asyncio.shield(closing), 0.5)
        assert not services[0]._background_tasks
        assert services[0].download_service._closed
        assert all(not task.done() for task in peer_tasks)
        assert not services[1].download_service._closed
        assert (
            await services[0].get_cached_category_image_with_download("Just Chatting")
            is None
        )
        assert not services[0]._background_tasks
        release.set()
        await asyncio.wait_for(asyncio.gather(*peer_tasks), 5)
        assert (
            services[1].download_service.images_base_dir
            / "categories/just_chatting.jpg"
        ).read_bytes() == b"fixture-image"
        assert not (
            services[0].download_service.images_base_dir
            / "categories/just_chatting.jpg"
        ).exists()
    finally:
        release.set()
        if closing is not None:
            await closing
        await runner.cleanup()
