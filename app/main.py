"""Composition root for the StreamVault ASGI application.

``create_app`` owns all composition: router registration, middleware
installation, lifespan wiring and static/frontend mounts.  The module-level
``app`` export is the pre-built process-scoped instance and exists only for
backward compatibility.
"""

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import FastAPI

from app.config.logging_config import setup_logging
from app.core.exceptions import install_exception_handlers
from app.lifespan import lifespan
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

logger = setup_logging()

_application: FastAPI | None = None


def _configure_app(
    application: FastAPI,
    settings: Any | None,
    service_overrides: Mapping[Callable[..., Any], Callable[..., Any]] | None,
) -> FastAPI:
    """Apply the stable StreamVault composition to one application instance."""
    if settings is not None:
        application.state.settings = settings
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
    application.add_middleware(AuthMiddleware)
    application.include_router(catchall_router)

    return application


def create_app(
    settings: Any | None = None,
    service_overrides: Mapping[Callable[..., Any], Callable[..., Any]] | None = None,
) -> FastAPI:
    """Create the ASGI application, preserving the process-scoped default export.

    Explicit settings or service overrides produce an isolated application for
    tests. Calling without either argument returns the compatibility instance
    used by ``app.main:app``.
    """
    global _application
    if settings is not None or service_overrides:
        application = FastAPI(
            title="StreamVault API",
            version="2.0.0",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
            openapi_url="/api/openapi.json",
            lifespan=lifespan,
        )
        return _configure_app(application, settings, service_overrides)

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
        )

    return _application


app = create_app()
