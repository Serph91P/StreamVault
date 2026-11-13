"""Factory startup/shutdown selects the actual automatic sync owner."""

import asyncio
import importlib

import pytest

from app import dependencies
from app.config.settings import Settings
from app.main import create_app
from app.models import Category, Streamer
from app.lifespan import _close_application_images
from app.services.system.supervisor import TaskSupervisor
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_sync_ownership

sync_owners = test_image_sync_ownership.sync_owners
artwork_owners = test_image_sync_ownership.artwork_owners
image_origin = test_image_sync_ownership.image_origin
startup = importlib.import_module("app.services.init.startup_init")


@pytest.mark.asyncio
async def test_factory_auto_image_initialization_and_shutdown_preserve_live_peer(
    sync_owners, monkeypatch
):
    _, facades, databases, _, base = sync_owners
    applications, actors = [], []
    supervisors = [TaskSupervisor("auto-first"), TaskSupervisor("auto-second")]

    async def unrelated_background(*args, **kwargs):
        return None

    async def queue_not_ready(*args, **kwargs):
        return False

    for name in (
        "initialize_vapid_keys",
        "initialize_background_queue_with_fixes",
        "start_session_cleanup_service",
        "start_zombie_recording_cleanup_service",
    ):
        monkeypatch.setattr(startup, name, unrelated_background)
    monkeypatch.setattr(startup, "verify_queue_readiness", queue_not_ready)
    try:
        for facade, database in zip(facades, databases, strict=True):
            with database.sync_session_factory() as session:
                session.query(Category).filter(
                    Category.name == "Fortnite"
                ).one().box_art_url = base + "/image"
                session.get(Streamer, 1).profile_image_url = base + "/image"
                session.commit()
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(facade.recordings_dir),
                    _env_file=None,
                ),
                database=database,
            )
            applications.append(app)
            assert app.state.auto_image_sync_service is None
            candidates = await asyncio.gather(
                *(
                    run_in_thread_pool(
                        dependencies._get_application_auto_image_sync_service, app
                    )
                    for _ in range(3)
                )
            )
            actor = candidates[0]
            actors.append(actor)
            assert all(candidate is actor for candidate in candidates)
            assert actor._images is app.state.image_service
            await startup.initialize_background_services(
                supervisor=supervisors[len(actors) - 1],
                session_factory=database.sync_session_factory,
                settings=app.state.settings,
                image_sync_service=actor,
            )
            await asyncio.wait_for(actor._sync_queue.join(), 5)
        assert actors[0] is not actors[1]
        assert all(actor.is_running() for actor in actors)
        for database in databases:
            with database.sync_session_factory() as session:
                assert session.get(Streamer, 1).profile_image_url.startswith(
                    "/recordings/.media/profiles/"
                )
                assert (
                    session.query(Category)
                    .filter(Category.name == "Fortnite")
                    .one()
                    .box_art_url.startswith("/api/media/categories/")
                )

        async def queue_shutdown():
            pass

        monkeypatch.setattr(startup, "shutdown_background_queue", queue_shutdown)
        await startup.shutdown_background_services(
            supervisor=supervisors[0], image_sync_service=actors[0]
        )
        assert not actors[0].is_running()
        assert actors[1].is_running()
        await actors[1].request_streamer_profile_sync(1, base + "/image")
        await asyncio.wait_for(actors[1]._sync_queue.join(), 5)
        await _close_application_images(applications[1])
        assert not actors[1].is_running()
        assert applications[1].state.auto_image_sync_service is None
    finally:
        for app in applications:
            await _close_application_images(app)
            await app.state.websocket_manager.close_all()
        for supervisor in supervisors:
            await supervisor.shutdown()
