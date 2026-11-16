"""Automatic sync actors own their queue/catalogue and never skip scanned pages."""

import asyncio
from threading import get_ident

import pytest

from app.models import Category, Streamer
from app.services.images.auto_image_sync_service import AutoImageSyncService
from tests import test_image_sync_ownership

sync_owners = test_image_sync_ownership.sync_owners
artwork_owners = test_image_sync_ownership.artwork_owners
image_origin = test_image_sync_ownership.image_origin


@pytest.mark.asyncio
async def test_auto_sync_workers_publish_only_owned_requests_and_complete_queue(
    sync_owners,
):
    _, facades, databases, queries, base = sync_owners
    workers = []
    try:
        for facade, database in zip(facades, databases, strict=True):
            with database.sync_session_factory() as session:
                session.query(Category).filter(
                    Category.name == "Fortnite"
                ).one().box_art_url = base + "/image"
                session.commit()
            workers.append(
                AutoImageSyncService(
                    image_service=facade, session_factory=database.sync_session_factory
                )
            )
        queries.clear()
        for index, worker in enumerate(workers):
            await worker.start_sync_worker()
            await worker.request_streamer_profile_sync(1, base + "/image")
            await worker.request_category_image_sync("Fortnite")
            await worker.request_stream_artwork_sync(1, 1, base + "/image")
            await asyncio.wait_for(worker._sync_queue.join(), 5)
            assert queries and get_ident() not in queries
            queries.clear()
            with databases[index].sync_session_factory() as session:
                assert session.get(Streamer, 1).profile_image_url.startswith(
                    "/recordings/.media/profiles/"
                )
                assert (
                    session.query(Category)
                    .filter(Category.name == "Fortnite")
                    .one()
                    .box_art_url.startswith("/api/media/categories/")
                )
            queries.clear()
            assert all(
                database.sync_engine.pool.checkedout() == 0 for database in databases
            )
            if index == 0:
                with databases[1].sync_session_factory() as session:
                    assert (
                        session.get(Streamer, 1).profile_image_url
                        == "/recordings/.media/profiles/missing.jpg"
                    )
                queries.clear()
        await workers[0].stop_sync_worker()
        assert workers[1].is_running()
    finally:
        for worker in workers:
            await worker.stop_sync_worker()


@pytest.mark.asyncio
async def test_auto_profile_pagination_does_not_end_on_a_fully_cached_page(sync_owners):
    _, facades, databases, queries, base = sync_owners
    database, facade = databases[0], facades[0]
    facade.profiles_dir.mkdir(parents=True)
    (facade.profiles_dir / "kept.jpg").write_bytes(b"cached-first-page")
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = "/data/images/profiles/kept.jpg"
        session.add(
            Streamer(
                id=2,
                twitch_id="second-source",
                username="second-source",
                profile_image_url=base + "/image",
            )
        )
        session.commit()
    worker = AutoImageSyncService(
        image_service=facade, session_factory=database.sync_session_factory
    )
    queries.clear()
    assert await worker.sync_all_streamers_paginated(batch_size=1) == 1
    assert worker._sync_queue.qsize() == 1
    request = worker._sync_queue.get_nowait()
    worker._sync_queue.task_done()
    assert request == {
        "type": "streamer_profile",
        "streamer_id": 2,
        "profile_image_url": base + "/image",
    }
    assert queries and get_ident() not in queries
    assert database.sync_engine.pool.checkedout() == 0
    assert (facade.profiles_dir / "kept.jpg").read_bytes() == b"cached-first-page"


@pytest.mark.asyncio
async def test_auto_category_pages_close_sessions_before_enqueue(
    sync_owners, monkeypatch
):
    _, facades, databases, queries, base = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        for category in session.query(Category).all():
            category.box_art_url = base + "/image"
        session.commit()
    worker = AutoImageSyncService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )
    native_request = worker.request_category_image_sync

    async def checked_request(*args):
        assert database.sync_engine.pool.checkedout() == 0
        await native_request(*args)

    monkeypatch.setattr(worker, "request_category_image_sync", checked_request)
    queries.clear()
    assert await worker.sync_all_categories_paginated(batch_size=1) == 2
    assert worker.get_queue_size() == 2
    assert queries and get_ident() not in queries
    assert {worker._sync_queue.get_nowait()["category_name"] for _ in range(2)} == {
        "Fortnite",
        "missing category",
    }
    for _ in range(2):
        worker._sync_queue.task_done()


@pytest.mark.asyncio
async def test_auto_legacy_missing_file_queues_plain_fallback_without_catalogue_write(
    sync_owners,
):
    _, facades, databases, queries, _ = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = "/data/images/profiles/absent.jpg"
        session.commit()
    worker = AutoImageSyncService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )
    queries.clear()
    assert await worker.sync_all_existing_streamers() == 1
    assert queries and get_ident() not in queries
    assert worker._sync_queue.get_nowait() == {
        "type": "streamer_profile",
        "streamer_id": 1,
        "profile_image_url": worker.TWITCH_PROFILE_URL_TEMPLATE.format(
            twitch_id="owner-0"
        ),
    }
    worker._sync_queue.task_done()
    with database.sync_session_factory() as session:
        assert (
            session.get(Streamer, 1).profile_image_url
            == "/data/images/profiles/absent.jpg"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "sync_all_existing_streamers",
        "sync_all_existing_categories",
        "sync_all_streamers_paginated",
    ],
)
async def test_auto_scan_database_failure_is_zero_and_retryable(sync_owners, method):
    from sqlalchemy import event

    _, facades, databases, _, base = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = base + "/image"
        session.query(Category).filter(
            Category.name == "Fortnite"
        ).one().box_art_url = base + "/image"
        session.commit()
    worker = AutoImageSyncService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )

    def unavailable(*_):
        raise OSError("synthetic catalogue failure")

    event.listen(database.sync_engine, "before_cursor_execute", unavailable)
    try:
        assert await getattr(worker, method)() == 0
        assert worker.get_queue_size() == 0
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", unavailable)
    assert database.sync_engine.pool.checkedout() == 0
    assert await getattr(worker, method)() == 1
    assert worker.get_queue_size() == 1
