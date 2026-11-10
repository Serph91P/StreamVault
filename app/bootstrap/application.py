"""Composition root for the StreamVault ASGI application.

``create_app`` owns all composition: router registration, middleware
installation, lifespan wiring and static/frontend mounts.  The module-level
``app`` export is the pre-built process-scoped instance and exists only for
backward compatibility.
"""

from collections.abc import Callable, Mapping
from functools import partial
from threading import Lock
from app.utils.cache import SimpleCache


from fastapi import FastAPI

from app.config.settings import Settings
from app.bootstrap.settings import resolve_app_settings
from app.core.exceptions import install_exception_handlers
from app.database import DatabaseLifecycle, database_lifecycle
from app.dependencies import _get_application_recovery_service
from app.services.communication.websocket_manager import (
    ConnectionManager,
    websocket_manager,
)
from app.services.core.automated_recovery_state import AutomatedRecoveryState
from app.services.init.background_queue_init import (
    BackgroundQueueManager,
    background_queue_manager,
)
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)
from app.services.background_queue_service import (
    BackgroundQueueService,
    background_queue_service,
)
from app.lifespan import lifespan
from app.tasks.websocket_broadcast_task import (
    WebSocketBroadcastTask,
    websocket_broadcast_task,
)
from app.middleware_all import install_http_middleware
from app.middleware.auth import AuthMiddleware

# ── routers ────────────────────────────────────────────────────────────────
from app.routes import (
    streamers,
    auth,
    twitch_auth,
    recording as recording_router,
    recordings,
    logging as logging_router,
    videos,
    images,
    api_images,
    background_queue,
    streams,
    status,
    health,
    notifications,
    proxy as proxy_router,
    push as push_router,
    admin as admin_router,
    migration as migration_router,
    version as version_router,
    api_keys as api_keys_router,
    live as live_router,
    categories,
)
from app.routes import settings as settings_router
from app.routes import eventsub as eventsub_router
from app.routes import realtime as realtime_router
from app.routes import system as system_router
from app.api import unified_recovery_endpoints
from app.api import automated_recovery_endpoints
from app.frontend import (
    spa_router,
    pwa_router,
    catchall_router,
    register_static_mounts,
)

_application: FastAPI | None = None


def _configure_app(
    application: FastAPI,
    settings: Settings | None,
    service_overrides: Mapping[Callable[..., object], Callable[..., object]] | None,
    *,
    legacy_default: bool = False,
    database: DatabaseLifecycle | None = None,
) -> FastAPI:
    """Apply the stable StreamVault composition to one application instance."""
    application.state.legacy_default = legacy_default
    if settings is not None:
        application.state.settings = settings
    if database is None:
        database = (
            database_lifecycle
            if legacy_default
            else DatabaseLifecycle(settings=settings)
        )
    application.state.database_lifecycle = database
    application.state.recording_manager = None
    application.state.startup_complete = False
    application.state.startup_failure = None
    application.state.startup_phases = []
    application.state.recording_status_cache = SimpleCache()
    application.state.login_throttle = auth.LoginThrottle()
    application.state.logging_service = None
    application.state.logging_service_lock = Lock()
    application.state.recording_manager_lock = Lock()
    application.state.twitch_api = None
    application.state.twitch_api_lock = Lock()
    application.state.twitch_oauth_service = None
    application.state.twitch_oauth_service_lock = Lock()
    application.state.twitch_token_service = None
    application.state.twitch_token_service_lock = Lock()
    application.state.live_streaming_service = None
    application.state.live_streaming_service_lock = Lock()
    application.state.streamlink_config_service = None
    application.state.streamlink_config_service_lock = Lock()
    application.state.unified_recovery_service = None
    application.state.unified_recovery_lock = Lock()
    application.state.automated_recovery_state = AutomatedRecoveryState()
    application.state.notification_service = None
    application.state.notification_service_lock = Lock()
    application.state.event_registry = None
    application.state.event_registry_lock = Lock()
    application.state.proxy_health_service = None
    application.state.proxy_health_service_lock = Lock()
    application.state.image_service = None
    application.state.image_service_lock = Lock()
    application.state.image_sync_service = None
    application.state.image_sync_service_lock = Lock()
    application.state.auto_image_sync_service = None
    application.state.auto_image_sync_service_lock = Lock()
    application.state.websocket_manager = (
        websocket_manager if legacy_default else ConnectionManager()
    )
    owned_database = database
    application.state.background_queue_service = (
        background_queue_service
        if legacy_default
        else BackgroundQueueService.for_application(
            application.state.websocket_manager,
            session_factory=lambda: owned_database.sync_session_factory(),
        )
    )
    application.state.background_queue_manager = (
        background_queue_manager
        if legacy_default
        else BackgroundQueueManager(
            queue_service=application.state.background_queue_service,
            task_handlers=PostProcessingTaskHandlers(
                session_factory=lambda: owned_database.sync_session_factory(),
                connection_manager=application.state.websocket_manager,
                recovery_service_factory=partial(
                    _get_application_recovery_service, application
                ),
            ),
        )
    )
    application.state.websocket_broadcast_task = (
        websocket_broadcast_task
        if legacy_default
        else WebSocketBroadcastTask(
            connection_manager=application.state.websocket_manager,
            session_factory=lambda: owned_database.sync_session_factory(),
            queue_service=application.state.background_queue_service,
        )
    )
    if service_overrides:
        application.dependency_overrides.update(service_overrides)

    # ── inline realtime / system / eventsub routers ────────────────────
    application.include_router(realtime_router.router)
    application.include_router(system_router.router)
    application.include_router(eventsub_router.router)

    # ── existing API routers (order preserved from legacy) ─────────────
    application.include_router(health.router)
    application.include_router(streamers.router)
    application.include_router(auth.router, prefix="/auth")
    application.include_router(settings_router.router)
    application.include_router(twitch_auth.router)
    application.include_router(recording_router.router)
    application.include_router(recordings.router, prefix="/api")
    application.include_router(logging_router.router)
    application.include_router(categories.router)
    application.include_router(videos.router)
    application.include_router(live_router.router)
    application.include_router(images.router)
    application.include_router(api_images.router)
    application.include_router(background_queue.router, prefix="/api")
    application.include_router(streams.router)
    application.include_router(status.router, prefix="/api")
    application.include_router(notifications.router)
    application.include_router(proxy_router.router)
    application.include_router(unified_recovery_endpoints.router)
    application.include_router(automated_recovery_endpoints.router)
    application.include_router(push_router.router)
    application.include_router(admin_router.router)
    application.include_router(migration_router.router)
    application.include_router(version_router.router, prefix="/api")
    application.include_router(api_keys_router.router)

    # ── frontend: explicit SPA routes → mounts → PWA routes ───────────
    application.include_router(spa_router)
    register_static_mounts(application)
    application.include_router(pwa_router)

    # ── exception handlers, middleware, then catch-all ──────────────────
    install_exception_handlers(application)
    install_http_middleware(application)
    if legacy_default:
        application.add_middleware(AuthMiddleware)
    else:
        application.add_middleware(
            AuthMiddleware,
            database=application.state.database_lifecycle,
            settings_provider=partial(resolve_app_settings, application),
        )
    application.include_router(catchall_router)

    return application


def create_app(
    settings: Settings | None = None,
    service_overrides: Mapping[Callable[..., object], Callable[..., object]]
    | None = None,
    *,
    database: DatabaseLifecycle | None = None,
) -> FastAPI:
    """Create the ASGI application, preserving the process-scoped default export.

    Explicit settings or service overrides produce an isolated application for
    tests. Calling without either argument returns the compatibility instance
    used by ``app.main:app``.
    """
    global _application
    if settings is not None or service_overrides or database is not None:
        application = FastAPI(
            title="StreamVault API",
            version="2.0.0",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
            openapi_url="/api/openapi.json",
            lifespan=lifespan,
        )
        return _configure_app(
            application, settings, service_overrides, database=database
        )

    if _application is None:
        _application = _configure_app(
            FastAPI(
                title="StreamVault API",
                version="2.0.0",
                docs_url="/api/docs",
                redoc_url="/api/redoc",
                openapi_url="/api/openapi.json",
                lifespan=lifespan,
            ),
            settings=None,
            service_overrides=None,
            legacy_default=True,
        )

    return _application


app = create_app()
