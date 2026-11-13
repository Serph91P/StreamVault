"""Factory image adapters share one lazy owner, including faulted startup close."""

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import DatabaseLifecycle
from app.lifespan import lifespan
from app.main import create_app
from app.services.system.migration_service import MigrationService
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_factory_image_provider_is_lazy_and_fault_shutdown_is_owner_local(
    tmp_path, monkeypatch
):
    applications, databases, images, workers, clients = [], [], [], [], []
    try:
        for name in ("first", "second"):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
            databases.append(database)
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(tmp_path / name / "recordings"),
                    LOGS_BASE_DIR=str(tmp_path / name / "logs"),
                    _env_file=None,
                ),
                database=database,
            )
            applications.append(app)
            assert database._sync_engine is None
            assert app.state.image_service is None
            assert app.state.image_sync_service is None
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            candidates = await asyncio.gather(
                *(
                    run_in_thread_pool(dependencies.get_image_service, connection)
                    for _ in range(3)
                )
            )
            image = candidates[0]
            images.append(image)
            assert all(candidate is image for candidate in candidates)
            assert image is app.state.image_service
            assert image.recordings_dir == tmp_path / name / "recordings"
            with image._session_factory() as session:
                assert session.get_bind() is database.sync_engine
            worker = await run_in_thread_pool(
                dependencies.get_image_sync_service, connection
            )
            workers.append(worker)
            assert worker._images is image
            with worker._session_factory() as session:
                assert session.get_bind() is database.sync_engine
            await worker.start_sync_worker()
            transport = await image.download_service.get_session()
            clients.append(await transport._get_client())
        assert images[0] is not images[1]
        assert workers[0] is not workers[1]
        monkeypatch.setattr(
            MigrationService,
            "for_engine",
            lambda _: SimpleNamespace(run_safe_migrations=lambda: False),
        )
        with pytest.raises(RuntimeError, match="migrations"):
            async with lifespan(applications[0]):
                pytest.fail("Faulted startup cannot become ready")
        assert clients[0].is_closed
        assert not clients[1].is_closed
        assert not workers[0].is_running()
        assert workers[1].is_running()
        assert applications[0].state.image_service is None
        assert applications[0].state.image_sync_service is None
        assert applications[1].state.image_service is images[1]
    finally:
        for worker in workers:
            await worker.stop_sync_worker()
        for image in images:
            await image.close()
        for app in applications:
            await app.state.websocket_manager.close_all()
        for database in databases:
            await database.adispose()
