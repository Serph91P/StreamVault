"""Image sync snapshots, queued requests and worker completion are owner-local."""

import asyncio
from threading import get_ident

import pytest

from app.config.constants import ASYNC_DELAYS
from app.config.settings import Settings
from app.models import Category, Streamer
from app.services.images.image_sync_service import ImageSyncService
from app.services.unified_image_service import UnifiedImageService
from tests import test_artwork_catalog_boundary

artwork_owners = test_artwork_catalog_boundary.artwork_owners
image_origin = test_artwork_catalog_boundary.image_origin


@pytest.fixture
async def sync_owners(artwork_owners):
    existing, databases, queries, _, _, base = artwork_owners
    images, workers = [], []
    try:
        for service, database in zip(existing, databases, strict=True):
            with database.sync_session_factory() as session:
                streamer = session.query(Streamer).one()
                streamer.profile_image_url = "/recordings/.media/profiles/missing.jpg"
                streamer.original_profile_image_url = base + "/image"
                session.add_all(
                    [
                        Category(name="Fortnite", twitch_id="popular"),
                        Category(name="missing category", twitch_id="missing"),
                    ]
                )
                session.commit()
            facade = UnifiedImageService(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(service.download_service.recordings_dir),
                    _env_file=None,
                ),
                session_factory=database.sync_session_factory,
            )
            images.append(facade)
            workers.append(
                ImageSyncService(
                    image_service=facade, session_factory=database.sync_session_factory
                )
            )
        queries.clear()
        yield workers, images, databases, queries, base
    finally:
        for worker in workers:
            await worker.stop_sync_worker()
        for image in images:
            await image.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,expected",
    [
        ("sync_all_existing_streamers", 1),
        ("sync_all_existing_categories", 2),
        ("sync_popular_categories_only", 1),
    ],
)
async def test_image_sync_reads_only_its_closed_scalar_catalogue(
    sync_owners, method, expected
):
    workers, _, databases, queries, base = sync_owners
    loop_thread = get_ident()
    for index, worker in enumerate(workers):
        await getattr(worker, method)()
        assert worker.get_queue_size() == expected
        assert queries and loop_thread not in queries
        queries.clear()
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        requests = [worker._sync_queue.get_nowait() for _ in range(expected)]
        for request in requests:
            assert all(
                value is None or isinstance(value, (str, int))
                for value in request.values()
            )
            worker._sync_queue.task_done()
        if method == "sync_all_existing_streamers":
            assert requests == [
                {
                    "type": "streamer_profile",
                    "streamer_id": 1,
                    "profile_image_url": base + "/image",
                }
            ]
        else:
            assert {request["category_name"] for request in requests} == (
                {"Fortnite"} if expected == 1 else {"Fortnite", "missing category"}
            )
        assert workers[1 - index].get_queue_size() == 0


@pytest.mark.asyncio
async def test_missing_image_scan_requests_only_absent_files_from_original_source(
    sync_owners,
):
    workers, images, _, queries, base = sync_owners
    assert await images[0].download_category_image("Fortnite", base + "/image")
    queries.clear()
    loop_thread = get_ident()
    await workers[0].check_and_sync_missing_images()
    requests = [
        workers[0]._sync_queue.get_nowait() for _ in range(workers[0].get_queue_size())
    ]
    for _ in requests:
        workers[0]._sync_queue.task_done()
    assert requests == [
        {
            "type": "streamer_profile",
            "streamer_id": 1,
            "profile_image_url": base + "/image",
        },
        {
            "type": "category_image",
            "category_name": "missing category",
            "image_url": None,
        },
    ]
    assert queries and loop_thread not in queries
    assert workers[1].get_queue_size() == 0


@pytest.mark.asyncio
async def test_image_sync_cancel_finishes_consumed_request_without_stopping_peer(
    sync_owners, monkeypatch
):
    workers, images, _, _, base = sync_owners
    entered_delay = asyncio.Event()
    native_sleep = asyncio.sleep

    async def observed_sleep(delay, *args, **kwargs):
        if delay == ASYNC_DELAYS.IMAGE_SYNC_REQUEST_DELAY:
            entered_delay.set()
        await native_sleep(delay, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", observed_sleep)
    try:
        await workers[0].start_sync_worker()
        await workers[1].start_sync_worker()
        await workers[0].request_streamer_profile_sync(1, base + "/image")
        async with asyncio.timeout(5):
            await entered_delay.wait()
        await workers[0].stop_sync_worker()
        assert workers[0]._sync_queue._unfinished_tasks == 0
        assert workers[1].is_running()
        await workers[1].request_stream_artwork_sync(1, 1, base + "/image")
        async with asyncio.timeout(5):
            await workers[1]._sync_queue.join()
        target = (
            images[1].download_service.images_base_dir
            / "artwork/streamer_1/stream_1.jpg"
        )
        assert target.read_bytes() == b"fixture-image-bytes"
    finally:
        await workers[0].stop_sync_worker()
        await workers[1].stop_sync_worker()
