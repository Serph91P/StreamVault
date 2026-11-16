"""Factory-owned catalog/media reads and durable queue admissions."""

from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest

from app.models import BackgroundTask, Stream
from app.services.media.video_catalog_service import VideoCatalogService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.fixture
async def media_applications(image_applications):
    applications, databases, clients, queries = image_applications
    for index, (application, database) in enumerate(zip(applications, databases)):
        root = Path(application.state.settings.RECORDING_DIRECTORY)
        media = root / "synthetic.ts"
        media.write_bytes(f"owner-{index}-media".encode())

        def seed():
            with database.sync_session_factory() as db:
                db.add(
                    Stream(
                        id=1,
                        streamer_id=1,
                        title=f"owner-{index}",
                        started_at=datetime.now(timezone.utc),
                        ended_at=datetime.now(timezone.utc),
                        recording_path=str(media),
                    )
                )
                db.commit()
                VideoCatalogService(db).reconcile_batch(limit=100)
                db.commit()

        await run_in_thread_pool(seed)
    yield image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["catalog", "metadata", "playback", "share"])
async def test_real_factories_read_only_owned_catalog_and_media(
    media_applications, surface
):
    _, databases, clients, queries = media_applications
    for index, client in enumerate(clients):
        queries.clear()
        if surface == "catalog":
            response = await client.get("/api/videos/catalog")
            assert response.status_code == 200, response.text
            assert [item["title"] for item in response.json()["items"]] == [
                f"owner-{index}"
            ]
        elif surface == "metadata":
            response = await client.get("/api/videos/1/metadata")
            assert response.status_code == 200, response.text
            assert response.json()["title"] == f"owner-{index}"
        elif surface == "playback":
            response = await client.get("/api/videos/1/stream")
            assert response.status_code == 200, response.text
            assert response.content == f"owner-{index}-media".encode()
        else:
            share = await client.post("/api/videos/1/share-token")
            assert share.status_code == 200, share.text
            from urllib.parse import urlparse

            url = urlparse(share.json()["share_url"])
            response = await client.get(url.path + "?" + url.query)
            assert response.status_code == 200, response.text
            assert response.content == f"owner-{index}-media".encode()
        assert queries and get_ident() not in [thread for thread, _ in queries]
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.asyncio
async def test_factory_queue_admission_persists_only_in_its_own_journal(
    image_applications,
):
    applications, databases, _, queries = image_applications
    identifiers = []
    for index, application in enumerate(applications):
        identifiers.append(
            await application.state.background_queue_service.enqueue_task(
                "synthetic-owned-journal", {"owner": index}
            )
        )

    def read(database):
        with database.sync_session_factory() as db:
            return [(row.id, row.payload) for row in db.query(BackgroundTask).all()]

    for index, database in enumerate(databases):
        rows = await run_in_thread_pool(read, database)
        assert rows == [(identifiers[index], {"owner": index})]
    assert get_ident() not in [thread for thread, _ in queries]
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.asyncio
async def test_catalog_maintenance_uses_closed_owning_factory(media_applications):
    from importlib import import_module
    from app.models import VideoCatalogEntry

    module = import_module("app.lifespan")
    _, databases, _, queries = media_applications
    for index, database in enumerate(databases):

        def reset():
            with database.sync_session_factory() as db:
                db.query(VideoCatalogEntry).delete()
                db.commit()

        await run_in_thread_pool(reset)
        await run_in_thread_pool(
            module._reconcile_catalog_batch, 0, database.sync_session_factory
        )

        def read():
            with database.sync_session_factory() as db:
                return db.query(VideoCatalogEntry).one().file_path

        assert await run_in_thread_pool(read) == str(
            Path(media_applications[0][index].state.settings.RECORDING_DIRECTORY)
            / "synthetic.ts"
        )
    assert get_ident() not in [thread for thread, _ in queries]
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize("public", [False, True])
async def test_factory_media_cannot_read_a_peer_root_even_if_its_catalog_claims_it(
    media_applications, public
):
    applications, databases, clients, _ = media_applications
    peer = Path(applications[1].state.settings.RECORDING_DIRECTORY) / "synthetic.ts"

    def claim_peer():
        with databases[0].sync_session_factory() as db:
            db.get(Stream, 1).recording_path = str(peer)
            db.commit()

    await run_in_thread_pool(claim_peer)
    if public:
        from urllib.parse import urlparse

        created = await clients[0].post("/api/videos/1/share-token")
        assert created.status_code == 200
        url = urlparse(created.json()["share_url"])
        path = url.path + "?" + url.query
        foreign = await clients[1].get(path)
        assert foreign.status_code == 401
    else:
        path = "/api/videos/1/stream"
    response = await clients[0].get(path)
    assert response.status_code == 403
    assert peer.read_bytes() == b"owner-1-media"
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
