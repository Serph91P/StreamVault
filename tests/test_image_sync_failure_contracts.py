"""Image-sync retries keep real catalogues and consumed queue accounting intact."""

import asyncio

import pytest
from sqlalchemy import event

from app.config.constants import ASYNC_DELAYS
from tests import test_image_sync_ownership as fixtures

sync_owners = fixtures.sync_owners
artwork_owners = fixtures.artwork_owners
image_origin = fixtures.image_origin


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,expected",
    [
        ("sync_all_existing_streamers", 1),
        ("sync_all_existing_categories", 2),
        ("sync_popular_categories_only", 1),
        ("check_and_sync_missing_images", 3),
    ],
)
async def test_catalog_failure_enqueues_nothing_releases_pool_and_retries(
    sync_owners, method, expected, caplog
):
    workers, _, databases, _, _ = sync_owners

    def unavailable(*_args):
        raise OSError("synthetic image catalog unavailable")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        await getattr(workers[0], method)()
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)
    assert workers[0].get_queue_size() == 0
    assert databases[0].sync_engine.pool.checkedout() == 0
    assert "synthetic image catalog unavailable" in caplog.text
    await getattr(workers[0], method)()
    assert workers[0].get_queue_size() == expected
    assert workers[1].get_queue_size() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("delayed", [False, True])
async def test_initial_sync_preserves_popular_only_delayed_selection(
    sync_owners, monkeypatch, delayed
):
    workers, _, databases, _, base = sync_owners
    native_sleep = asyncio.sleep
    delays = []

    async def observe_delay(delay):
        delays.append(delay)
        await native_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", observe_delay)
    await getattr(workers[0], "_initial_sync_delayed" if delayed else "_initial_sync")()
    assert delays == ([ASYNC_DELAYS.IMAGE_SYNC_INTERVAL] if delayed else [])
    requests = []
    while workers[0].get_queue_size():
        requests.append(workers[0]._sync_queue.get_nowait())
        workers[0]._sync_queue.task_done()
    assert requests[0] == {
        "type": "streamer_profile",
        "streamer_id": 1,
        "profile_image_url": base + "/image",
    }
    assert {item["category_name"] for item in requests[1:]} == (
        {"Fortnite"} if delayed else {"Fortnite", "missing category"}
    )
    assert databases[0].sync_engine.pool.checkedout() == 0
    assert workers[1].get_queue_size() == 0


@pytest.mark.asyncio
async def test_malformed_requests_do_not_download_and_unknown_request_is_completed(
    sync_owners, caplog
):
    workers, images, _, _, _ = sync_owners
    worker = workers[0]
    before = list(images[0].download_service.images_base_dir.rglob("*.jpg"))
    for request in (
        {"type": "streamer_profile", "streamer_id": 1},
        {"type": "category_image"},
        {"type": "stream_artwork", "stream_id": 1, "streamer_id": 1},
    ):
        await worker._process_sync_request(request)
    assert list(images[0].download_service.images_base_dir.rglob("*.jpg")) == before
    await worker.start_sync_worker()
    original = worker._sync_task
    await worker.start_sync_worker()
    assert worker._sync_task is original
    await worker._sync_queue.put({"type": "unsupported"})
    await asyncio.wait_for(worker._sync_queue.join(), 5)
    assert "Unknown sync request type: unsupported" in caplog.text
    await worker.stop_sync_worker()
    assert original.done() and not worker.is_running()
    assert worker._sync_queue._unfinished_tasks == 0
    assert list(images[0].download_service.images_base_dir.rglob("*.jpg")) == before
