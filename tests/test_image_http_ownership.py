"""Real factory/auth requests must use only their image catalogue and disk root."""

from contextlib import AsyncExitStack
from secrets import token_urlsafe
from threading import get_ident

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import event

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.lifespan import _close_application_images
from app.main import create_app
from app.models import Category, Streamer
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_boundary

image_origin = test_image_http_boundary.image_origin


@pytest.fixture
async def image_applications(tmp_path):
    applications, databases, clients, queries = [], [], [], []
    async with AsyncExitStack() as stack:
        try:
            for index in range(2):
                name = f"owner-{index}"
                root = tmp_path / name
                database = DatabaseLifecycle(f"sqlite:///{root}.db")
                databases.append(database)
                app = create_app(
                    settings=Settings(
                        ENVIRONMENT="test",
                        auth_jwt_secret=SecretStr(token_urlsafe(48)),
                        RECORDING_DIRECTORY=str(root),
                        _env_file=None,
                    ),
                    database=database,
                )
                applications.append(app)
                with database.sync_engine.begin() as connection:
                    Base.metadata.create_all(connection)
                with database.sync_session_factory() as session:
                    session.add(
                        Streamer(
                            id=1,
                            twitch_id=name,
                            username=name,
                            profile_image_url=f"https://images.invalid/{name}.jpg",
                        )
                    )
                    session.commit()
                for directory in ("profiles", "categories", "artwork/streamer_1"):
                    destination = root / ".media" / directory
                    destination.mkdir(parents=True)
                    (destination / "probe.jpg").write_bytes(name.encode())
                client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app),
                        base_url="https://localhost:8000",
                    )
                )
                clients.append(client)
                credentials = {"username": "image-admin", "password": token_urlsafe(32)}
                assert (
                    await client.post("/auth/setup", json=credentials)
                ).status_code == 200
                assert (
                    await client.post("/auth/login", json=credentials)
                ).status_code == 200
                event.listen(
                    database.sync_engine,
                    "before_cursor_execute",
                    lambda *args: queries.append((get_ident(), args[2])),
                )
            yield applications, databases, clients, queries
        finally:
            for app in applications:
                await _close_application_images(app)
                await app.state.websocket_manager.close_all()
            for database in databases:
                await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("directory", ["profiles", "categories", "artwork/1"])
async def test_image_file_routes_serve_only_the_configured_owner(
    image_applications, directory
):
    _, _, clients, _ = image_applications
    for index, client in enumerate(clients):
        response = await client.get(f"/data/images/{directory}/probe.jpg")
        assert response.status_code == 200, response.text
        assert response.content == f"owner-{index}".encode()
        missing = await client.get(f"/data/images/{directory}/missing.jpg")
        assert missing.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/data/images/profile/1", "/api/images/streamer/1", "/api/images/streamers"],
)
async def test_image_profile_routes_project_the_owned_catalogue_off_loop(
    image_applications, path
):
    _, databases, clients, queries = image_applications
    for index, client in enumerate(clients):
        queries.clear()
        response = await client.get(path)
        assert response.status_code == 200, response.text
        data = response.json()
        data = data[0] if isinstance(data, list) else data
        assert data["image_url"] == f"https://images.invalid/owner-{index}.jpg"
        catalogue_threads = [
            thread for thread, sql in queries if "FROM streamers" in sql
        ]
        assert catalogue_threads and get_ident() not in catalogue_threads
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )


@pytest.mark.asyncio
async def test_image_sync_http_status_uses_its_own_queue(image_applications):
    applications, _, clients, _ = image_applications
    for index, app in enumerate(applications):
        worker = await run_in_thread_pool(
            dependencies._get_application_image_sync_service, app
        )
        for _ in range(index + 1):
            await worker.request_category_image_sync("synthetic")
    for index, client in enumerate(clients):
        response = await client.get("/api/images/sync/queue-status")
        assert response.status_code == 200
        assert response.json() == {
            "queue_size": index + 1,
            "is_running": False,
            "service_initialized": True,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,kind",
    [
        ("/api/images/streamer/1/download", "profiles"),
        ("/api/images/category/downloaded/download", "categories"),
        ("/data/images/sync/profiles", "profiles"),
        ("/data/images/sync/categories", "categories"),
        ("/api/images/sync", "profiles"),
        ("/api/migration/images/refresh/streamer/1", "profiles"),
        ("/api/migration/images/refresh/category/downloaded", "categories"),
        ("/api/migration/images/refresh", "profiles"),
    ],
)
async def test_image_http_background_action_publishes_only_owned_files(
    image_applications, image_origin, path, kind
):
    applications, databases, clients, _ = image_applications
    base, _ = image_origin
    for database in databases:
        with database.sync_session_factory() as session:
            session.get(Streamer, 1).profile_image_url = base + "/image"
            session.add(
                Category(
                    name="downloaded",
                    twitch_id="downloaded",
                    box_art_url=base + "/image",
                )
            )
            session.commit()
    for index, client in enumerate(clients):
        response = await client.post(path)
        assert response.status_code == 200, response.text
        if "/migration/" in path:
            assert response.json()["success"] is True
        root = applications[index].state.image_service.images_base_dir / kind
        published = [file for file in root.glob("*.jpg") if file.name != "probe.jpg"]

        assert published and all(
            file.read_bytes() == b"fixture-image-bytes" for file in published
        )
        if index == 0:
            peer = applications[1].state.settings.RECORDING_DIRECTORY
            from pathlib import Path

            assert (
                Path(peer) / ".media" / kind / "probe.jpg"
            ).read_bytes() == b"owner-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/data/images/profile/99", "/api/images/streamer/99"])
async def test_image_http_missing_catalogue_row_is_404(image_applications, path):
    _, _, clients, _ = image_applications
    for client in clients:
        assert (await client.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_refresh_http_exposes_failed_downloads_without_success(
    image_applications, image_origin
):
    _, databases, clients, _ = image_applications
    base, _ = image_origin
    with databases[0].sync_session_factory() as session:
        session.get(Streamer, 1).profile_image_url = base + "/denied"
        session.add(
            Category(
                name="downloaded", twitch_id="downloaded", box_art_url=base + "/denied"
            )
        )
        session.commit()
    response = await clients[0].post("/api/migration/images/refresh")
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["stats"] == {
        "profile_images_refreshed": 0,
        "category_images_refreshed": 0,
        "stream_artwork_refreshed": 0,
        "errors": 2,
    }
