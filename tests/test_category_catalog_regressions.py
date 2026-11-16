"""Exercise category publication failures, reloads and interrupted owned workers."""

import asyncio
from threading import Event

import pytest
from sqlalchemy import event

from app.models import Category
from app.services.images.category_image_service import CategoryImageService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_category_catalog_boundary

category_owners = test_category_catalog_boundary.category_owners
image_origin = test_category_catalog_boundary.image_origin


@pytest.mark.asyncio
async def test_category_reload_missing_local_file_and_failed_provider(category_owners):
    services, databases, _, _, _, base = category_owners
    service, database = services[0], databases[0]
    assert await service.update_category_image("Just Chatting", base + "/image")
    reloaded = CategoryImageService(
        service.download_service, session_factory=database.sync_session_factory
    )
    try:
        local = "/api/media/categories/just_chatting.jpg"
        assert (
            await run_in_thread_pool(
                reloaded.get_cached_category_image, "Just Chatting"
            )
            == local
        )
        assert await reloaded.download_category_image("Just Chatting") == local
        assert (
            await reloaded.get_cached_category_image_with_download("Just Chatting")
            == local
        )
        assert await reloaded.get_cached_category_image_with_download("Missing") is None
        assert await reloaded.download_category_image("") is None
        assert await reloaded.download_category_image("Missing") is None
        await run_in_thread_pool(
            (
                service.download_service.images_base_dir
                / "categories/just_chatting.jpg"
            ).unlink
        )
        reloaded._category_cache.clear()
        assert (
            await run_in_thread_pool(
                reloaded.get_cached_category_image, "Just Chatting"
            )
            is None
        )
        assert await reloaded.download_category_image("Just Chatting") is None
        assert not await reloaded.update_category_image("Missing", base + "/image")
        assert (
            await reloaded.download_category_image("Denied", base + "/denied") is None
        )
        assert (
            await reloaded.download_category_image("Denied", base + "/denied") is None
        )
        assert await reloaded.sync_all_category_images() == {
            "downloaded": 0,
            "skipped": 1,
            "failed": 0,
        }
        assert await reloaded.bulk_sync_categories(
            [
                {"id": "local", "name": "Local", "box_art_url": local},
                {"id": "denied", "name": "Denied", "box_art_url": base + "/denied"},
                {"name": "Ignored"},
            ]
        ) == {"updated": 2, "downloaded": 0, "failed": 1}
        with database.sync_session_factory() as session:
            assert (
                session.query(Category).filter_by(name="Local").one().box_art_url
                == local
            )
            assert (
                session.query(Category).filter_by(name="Denied").one().box_art_url
                == base + "/denied"
            )
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await reloaded.close()


@pytest.mark.asyncio
async def test_category_commit_failure_rolls_back_the_entire_bulk_and_retries(
    category_owners,
):
    services, databases, _, _, _, base = category_owners
    service, database = services[0], databases[0]
    entries = [
        {"id": name, "name": name, "box_art_url": base + "/image"}
        for name in ["First", "Second"]
    ]

    def fail_commit(_session):
        raise RuntimeError("synthetic commit failure")

    # A real transaction reaches flush/commit; the Session context owns rollback.
    session_type = database.sync_session_factory.class_
    event.listen(session_type, "before_commit", fail_commit)
    try:
        assert await service.bulk_sync_categories(entries) == {
            "updated": 0,
            "downloaded": 0,
            "failed": 0,
        }
    finally:
        event.remove(session_type, "before_commit", fail_commit)
    with database.sync_session_factory() as session:
        assert session.query(Category).count() == 1
    assert await service.bulk_sync_categories(entries) == {
        "updated": 2,
        "downloaded": 2,
        "failed": 0,
    }
    with database.sync_session_factory() as session:
        assert session.query(Category).count() == 3
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("through_facade", [False, True])
async def test_repeated_category_close_cancellation_drains_actual_filesystem_worker(
    category_owners, monkeypatch, through_facade
):
    services, _, _, _, _, base = category_owners
    service, peer = services
    close = service.close
    if through_facade:
        from app.services.unified_image_service import UnifiedImageService

        facade = UnifiedImageService()
        facade.category_service = service
        facade.download_service = service.download_service
        close = facade.close
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = Event()
    native_prepare = service._prepare_download

    def held(*arguments):
        value = native_prepare(*arguments)
        loop.call_soon_threadsafe(entered.set)
        if not release.wait(5):
            raise TimeoutError("fixture worker release missing")
        return value

    monkeypatch.setattr(service, "_prepare_download", held)
    closing = None
    try:
        assert (
            await service.get_cached_category_image_with_download("Just Chatting")
            == base + "/image"
        )
        await asyncio.wait_for(entered.wait(), 5)
        closing = asyncio.create_task(close())
        await asyncio.sleep(0.05)
        closing.cancel()
        await asyncio.sleep(0.05)
        closing.cancel()
        await asyncio.sleep(0.05)
        assert not closing.done(), (
            "cancellation must not abandon the real filesystem worker"
        )
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await closing
        assert not service._background_tasks and service.download_service._closed
        assert not peer.download_service._closed
        assert await peer.download_category_image("Just Chatting")
    finally:
        release.set()
        if closing is not None:
            await asyncio.gather(closing, return_exceptions=True)
