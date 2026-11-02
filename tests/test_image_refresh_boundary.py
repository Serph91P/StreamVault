"""Refresh producers close owner catalogues before file/HTTP publication."""

from threading import get_ident

import pytest

from app.models import Category, Streamer
from app.services.images.image_refresh_service import ImageRefreshService
from tests import test_image_sync_ownership

sync_owners = test_image_sync_ownership.sync_owners
artwork_owners = test_image_sync_ownership.artwork_owners
image_origin = test_image_sync_ownership.image_origin


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["all", "profile", "category"])
async def test_refresh_uses_only_closed_owner_snapshots_and_committed_results(
    sync_owners, operation, monkeypatch
):
    _, facades, databases, queries, base = sync_owners
    from pathlib import Path

    file_threads = []
    native_stat = Path.stat

    def observed_stat(path, *args, **kwargs):
        if "/.media/" in str(path):
            file_threads.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", observed_stat)
    refreshers, requests = [], []
    for index, (facade, database) in enumerate(zip(facades, databases, strict=True)):
        with database.sync_session_factory() as session:
            streamer = session.get(Streamer, 1)
            streamer.profile_image_url = base + "/image"
            session.query(Category).filter(
                Category.name == "Fortnite"
            ).one().box_art_url = base + "/image"
            session.commit()
        native_session = facade.download_service.get_session

        async def checked_session(native=native_session, owner=index):
            assert all(
                database.sync_engine.pool.checkedout() == 0 for database in databases
            )
            requests.append(owner)
            return await native()

        monkeypatch.setattr(facade.download_service, "get_session", checked_session)
        refreshers.append(
            ImageRefreshService(
                image_service=facade, session_factory=database.sync_session_factory
            )
        )
    queries.clear()
    for index, refresher in enumerate(refreshers):
        if operation == "all":
            result = await refresher.check_and_refresh_missing_images()
            assert result == {
                "profile_images_refreshed": 1,
                "category_images_refreshed": 1,
                "stream_artwork_refreshed": 1,
                "errors": 0,
            }
        elif operation == "profile":
            assert await refresher.refresh_specific_streamer(1)
            assert not await refresher.refresh_specific_streamer(99)
        else:
            assert await refresher.refresh_specific_category("Fortnite")
            assert not await refresher.refresh_specific_category("absent")
        assert queries and get_ident() not in queries
        assert get_ident() not in file_threads
        if operation == "all":
            assert file_threads
        file_threads.clear()
        queries.clear()
        assert requests and set(requests) == {index}
        requests.clear()
        with databases[index].sync_session_factory() as session:
            if operation != "category":
                assert session.get(Streamer, 1).profile_image_url.startswith(
                    "/recordings/.media/profiles/"
                )
            if operation != "profile":
                assert (
                    session.query(Category)
                    .filter(Category.name == "Fortnite")
                    .one()
                    .box_art_url.startswith("/api/media/categories/")
                )
        queries.clear()
        if index == 0:
            with databases[1].sync_session_factory() as session:
                assert session.get(Streamer, 1).profile_image_url == base + "/image"
                assert (
                    session.query(Category)
                    .filter(Category.name == "Fortnite")
                    .one()
                    .box_art_url
                    == base + "/image"
                )
            queries.clear()


@pytest.mark.asyncio
async def test_refresh_retains_cached_files_and_reports_no_work_on_repeat(sync_owners):
    _, facades, databases, _, base = sync_owners
    database, facade = databases[0], facades[0]
    refresher = ImageRefreshService(
        image_service=facade, session_factory=database.sync_session_factory
    )
    with database.sync_session_factory() as session:
        session.query(Category).filter(
            Category.name == "Fortnite"
        ).one().box_art_url = base + "/image"
        session.commit()
    first = await refresher.check_and_refresh_missing_images()
    assert first == {
        "profile_images_refreshed": 1,
        "category_images_refreshed": 1,
        "stream_artwork_refreshed": 1,
        "errors": 0,
    }
    before = {
        str(path): path.read_bytes() for path in facade.images_base_dir.rglob("*.jpg")
    }
    assert await refresher.check_and_refresh_missing_images() == {
        "profile_images_refreshed": 0,
        "category_images_refreshed": 0,
        "stream_artwork_refreshed": 0,
        "errors": 0,
    }
    assert before == {
        str(path): path.read_bytes() for path in facade.images_base_dir.rglob("*.jpg")
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "_refresh_missing_profile_images",
        "_refresh_missing_category_images",
        "_refresh_missing_stream_artwork",
    ],
)
async def test_refresh_catalogue_read_failure_is_visible_and_retryable(
    sync_owners, method
):
    from sqlalchemy import event

    _, facades, databases, _, _ = sync_owners
    database = databases[0]
    refresher = ImageRefreshService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )

    def unavailable(*_):
        raise OSError("synthetic catalogue unavailable")

    event.listen(database.sync_engine, "before_cursor_execute", unavailable)
    try:
        assert await getattr(refresher, method)() == {"refreshed": 0, "errors": 1}
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", unavailable)
    result = await getattr(refresher, method)()
    assert result["errors"] == 0
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_refresh_specific_http_denial_never_reports_success(sync_owners):
    _, facades, databases, _, base = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = base + "/denied"
        session.query(Category).filter(
            Category.name == "Fortnite"
        ).one().box_art_url = base + "/denied"
        session.commit()
    refresher = ImageRefreshService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )
    assert not await refresher.refresh_specific_streamer(1)
    assert not await refresher.refresh_specific_category("Fortnite")
    with database.sync_session_factory() as session:
        assert session.get(Streamer, 1).profile_image_url == base + "/denied"
        assert (
            session.query(Category)
            .filter(Category.name == "Fortnite")
            .one()
            .box_art_url
            == base + "/denied"
        )
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_refresh_cancellation_drains_its_real_catalogue_worker_before_return(
    sync_owners,
):
    import asyncio
    from threading import Event
    from sqlalchemy import event

    _, facades, databases, _, base = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = base + "/image"
        session.commit()
    refresher = ImageRefreshService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )
    entered, release = Event(), Event()

    def held(*args):
        if "FROM streamers" in args[2]:
            entered.set()
            assert release.wait(5)

    event.listen(database.sync_engine, "before_cursor_execute", held)
    task = asyncio.create_task(refresher.refresh_specific_streamer(1))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        assert database.sync_engine.pool.checkedout() == 1
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        event.remove(database.sync_engine, "before_cursor_execute", held)
    assert database.sync_engine.pool.checkedout() == 0
    assert await refresher.refresh_specific_streamer(1)


@pytest.mark.asyncio
async def test_bulk_refresh_counts_real_download_failures_without_false_success(
    sync_owners,
):
    from app.models import StreamMetadata

    _, facades, databases, _, base = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = base + "/denied"
        session.query(Category).filter(
            Category.name == "Fortnite"
        ).one().box_art_url = base + "/denied"
        session.query(StreamMetadata).one().thumbnail_url = base + "/denied"
        session.commit()
    refresher = ImageRefreshService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )
    assert await refresher.check_and_refresh_missing_images() == {
        "profile_images_refreshed": 0,
        "category_images_refreshed": 0,
        "stream_artwork_refreshed": 0,
        "errors": 3,
    }
    with database.sync_session_factory() as session:
        assert session.get(Streamer, 1).profile_image_url == base + "/denied"
        assert (
            session.query(Category)
            .filter(Category.name == "Fortnite")
            .one()
            .box_art_url
            == base + "/denied"
        )
        assert session.query(StreamMetadata).one().thumbnail_url == base + "/denied"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,identity",
    [("refresh_specific_streamer", 1), ("refresh_specific_category", "Fortnite")],
)
async def test_specific_refresh_database_failure_returns_false_and_allows_retry(
    sync_owners, method, identity
):
    from sqlalchemy import event

    _, facades, databases, _, base = sync_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = base + "/image"
        session.query(Category).filter(
            Category.name == "Fortnite"
        ).one().box_art_url = base + "/image"
        session.commit()
    refresher = ImageRefreshService(
        image_service=facades[0], session_factory=database.sync_session_factory
    )

    def unavailable(*_):
        raise OSError("synthetic read failure")

    event.listen(database.sync_engine, "before_cursor_execute", unavailable)
    try:
        assert not await getattr(refresher, method)(identity)
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", unavailable)
    assert database.sync_engine.pool.checkedout() == 0
    assert await getattr(refresher, method)(identity)
