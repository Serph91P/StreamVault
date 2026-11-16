"""Lazy factory bindings and fault-shutdown ownership, not full PG startup."""

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.lifespan import lifespan
from app.main import create_app
from app.services.system.migration_service import MigrationService
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_factory_recovery_provider_shares_only_its_owned_http_and_closes_on_fault(
    tmp_path, monkeypatch
):
    applications, databases, services, transports = [], [], [], []
    try:
        for name in ("first", "second"):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
            databases.append(database)
            root = tmp_path / name
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test",
                    TWITCH_APP_ID=name,
                    TWITCH_APP_SECRET="fixture-secret",
                    RECORDING_DIRECTORY=str(root / "recordings"),
                    LOGS_BASE_DIR=str(root / "logs"),
                    _env_file=None,
                ),
                database=database,
            )
            applications.append(app)
            assert database._sync_engine is None
            assert app.state.twitch_api is None
            assert app.state.unified_recovery_service is None
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            candidates = await asyncio.gather(
                *(
                    run_in_thread_pool(
                        dependencies.get_application_recovery_service, connection
                    )
                    for _ in range(3)
                )
            )
            service = candidates[0]
            services.append(service)
            assert all(candidate is service for candidate in candidates)
            assert service is app.state.unified_recovery_service
            assert service.twitch_api is app.state.twitch_api
            assert service.recording_manager is app.state.recording_manager
            assert service.queue_service is app.state.background_queue_service
            assert service.settings is app.state.settings
            assert service.twitch_api.client_id == name
            with service._sessions() as session:
                assert session.get_bind() is database.sync_engine
            transports.append(await service.twitch_api._http_client._get_client())
        assert services[0] is not services[1]
        assert services[0].twitch_api is not services[1].twitch_api
        monkeypatch.setattr(
            MigrationService,
            "for_engine",
            lambda _: SimpleNamespace(run_safe_migrations=lambda: False),
        )
        with pytest.raises(RuntimeError, match="migrations"):
            async with lifespan(applications[0]):
                pytest.fail("Faulted startup cannot become ready")
        assert transports[0].is_closed
        assert not transports[1].is_closed
        assert applications[0].state.twitch_api is None
        assert applications[0].state.unified_recovery_service is None
        assert applications[1].state.unified_recovery_service is services[1]
    finally:
        for service in services:
            await service.twitch_api.close()
        for app in applications:
            await app.state.websocket_manager.close_all()
        for database in databases:
            await database.adispose()
