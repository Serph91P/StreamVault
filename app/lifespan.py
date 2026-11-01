import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.config.constants import TIMEOUTS
from app.config.logging_config import setup_logging
from app.config.settings import Settings
from app.database import SessionLocal, database_lifecycle
from app.dependencies import (
    get_event_registry,
    get_lifespan_service,
    get_recording_manager,
)

from app.services.core.session_maintenance import cleanup_expired_sessions
from app.services.images.image_sync_service import image_sync_service
from app.services.system.supervisor import TaskSupervisor
from app.tasks.websocket_broadcast_task import websocket_broadcast_task
from app.utils.async_db_utils import run_in_thread_pool

logger = setup_logging()


async def _run_session_cleanup(
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
) -> None:
    """Periodically clean up expired sessions without retaining a DB lock."""

    while True:
        await asyncio.sleep(6 * 3600)
        try:
            expired_count = await run_in_thread_pool(
                cleanup_expired_sessions, session_factory, settings
            )
            if expired_count:
                logger.info("Cleaned up %s expired sessions", expired_count)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Session cleanup failed (%s)", type(error).__name__, exc_info=True
            )


async def _run_recording_cleanup() -> None:
    from app.services.system.cleanup_service import CleanupService

    while True:
        try:
            await CleanupService.run_scheduled_cleanup()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Scheduled recording cleanup failed (%s)",
                type(error).__name__,
                exc_info=True,
            )
        await asyncio.sleep(12 * 3600)


async def _stop_event_registry(event_registry) -> None:
    eventsub = getattr(event_registry, "eventsub", None)
    if eventsub is not None and hasattr(eventsub, "stop"):
        await eventsub.stop()
    elif hasattr(event_registry, "cleanup"):
        await event_registry.cleanup()


async def _shutdown_step(name: str, operation) -> None:
    try:
        await operation()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.error("Shutdown step %s failed (%s)", name, type(error).__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run ordered startup phases and reverse, idempotent shutdown ownership."""
    if app is None:
        app = SimpleNamespace(state=SimpleNamespace(), dependency_overrides={})
    supervisor = TaskSupervisor("application")
    runtime_database = getattr(app.state, "database_lifecycle", database_lifecycle)
    legacy_context = (
        getattr(app.state, "legacy_default", True)
        and runtime_database is database_lifecycle
    )
    app.state.task_supervisor = supervisor
    app.state.startup_phases = []
    event_registry = None
    recording_manager = None
    background_services_started = False
    image_sync_started = False
    websocket_started = False
    broadcast_task = getattr(
        app.state, "websocket_broadcast_task", websocket_broadcast_task
    )
    proxy_started = False

    def phase(name: str) -> None:
        app.state.startup_phases.append(name)
        logger.info("Startup phase complete: %s", name)

    from app.bootstrap.settings import resolve_app_settings

    runtime_settings = resolve_app_settings(app)
    setup_logging(runtime_settings)
    logger.info("Starting application initialization")
    try:
        from app.bootstrap.storage import prepare_storage_directories

        await run_in_thread_pool(prepare_storage_directories, runtime_settings)
        from app.services.system.migration_service import MigrationService

        def run_migrations() -> bool:
            if legacy_context:
                return MigrationService.run_safe_migrations()
            return MigrationService.for_engine(
                runtime_database.sync_engine
            ).run_safe_migrations()

        if not await run_in_thread_pool(run_migrations):
            raise RuntimeError("Database migrations did not complete successfully")
        phase("migrations")

        # Persistent identities must only be touched after a current schema exists.
        from app.services.system.persistent_key_service import bootstrap_persistent_keys

        def bootstrap_keys() -> None:
            if legacy_context:
                bootstrap_persistent_keys()
            else:
                from app.services.system.persistent_key_service import (
                    PersistentKeyBootstrapService,
                )

                PersistentKeyBootstrapService(
                    runtime_database.sync_session_factory
                ).bootstrap(runtime_settings)

        await run_in_thread_pool(bootstrap_keys)
        phase("persistent-identities")

        from app.services.migration.image_migration_service import (
            image_migration_service,
        )

        try:
            if (
                image_migration_service.old_images_dir.exists()
                or image_migration_service.old_artwork_dir.exists()
            ):
                await image_migration_service.migrate_all_images()
        except Exception as error:
            logger.warning("Image migration skipped (%s)", type(error).__name__)

        from app.services.system.streamlink_config_service import (
            streamlink_config_service,
        )

        try:
            await streamlink_config_service.update_config_from_settings()
        except Exception as error:
            logger.warning(
                "Streamlink config generation skipped (%s)", type(error).__name__
            )

        from app.services.images.image_refresh_service import image_refresh_service

        supervisor.create_task(
            "image-refresh", image_refresh_service.check_and_refresh_missing_images()
        )
        phase("optional-preparation")

        recording_manager = await run_in_thread_pool(
            get_lifespan_service(app, get_recording_manager)
        )
        app.state.recording_manager = recording_manager
        reconciled_leases = await recording_manager.reconcile_leases()
        logger.info("Reconciled %s stale Twitch upstream leases", reconciled_leases)

        event_registry = await get_lifespan_service(app, get_event_registry)()
        await event_registry.initialize_eventsub()
        phase("core-services")

        from app.services.system.logging_service import logging_service

        supervisor.create_task(
            "log-cleanup", logging_service._schedule_cleanup(interval_hours=24)
        )
        supervisor.create_task("recording-cleanup", _run_recording_cleanup())
        supervisor.create_task(
            "session-cleanup",
            _run_session_cleanup(
                SessionLocal
                if legacy_context
                else runtime_database.sync_session_factory,
                runtime_settings,
            ),
        )

        from app.services.init.startup_init import initialize_background_services

        await initialize_background_services(
            supervisor=supervisor,
            session_factory=SessionLocal
            if legacy_context
            else runtime_database.sync_session_factory,
            settings=runtime_settings,
        )
        background_services_started = True

        await image_sync_service.start_sync_worker()
        image_sync_started = True
        await broadcast_task.start()
        websocket_started = True

        from app.services.proxy.proxy_health_service import proxy_health_service

        await proxy_health_service.start()
        proxy_started = True
        phase("background-services")
        phase("ready")
        logger.info("Application startup complete")

        yield
    finally:
        logger.info("Starting application shutdown")

        if proxy_started:
            from app.services.proxy.proxy_health_service import proxy_health_service

            await _shutdown_step("proxy-health", proxy_health_service.stop)
        if websocket_started:
            await _shutdown_step("websocket-broadcast", broadcast_task.stop)
        if image_sync_started:
            await _shutdown_step("image-sync", image_sync_service.stop_sync_worker)
        if background_services_started:
            from app.services.init.startup_init import shutdown_background_services

            await _shutdown_step(
                "background-services",
                lambda: shutdown_background_services(supervisor=supervisor),
            )

        await supervisor.shutdown(process_timeout=TIMEOUTS.GRACEFUL_SHUTDOWN)

        if event_registry is not None:
            await _shutdown_step(
                "eventsub", lambda: _stop_event_registry(event_registry)
            )

        from app.services.live_streaming_service import live_streaming_service

        await _shutdown_step("live-streaming", live_streaming_service.stop)
        if recording_manager is not None:
            await _shutdown_step(
                "recording-manager",
                lambda: recording_manager.shutdown(timeout=TIMEOUTS.GRACEFUL_SHUTDOWN),
            )
        connection_manager = getattr(app.state, "websocket_manager", None)
        if connection_manager is not None:
            await _shutdown_step("websocket-connections", connection_manager.close_all)
        await _shutdown_step("database", runtime_database.adispose)
        logger.info("Application shutdown complete")
