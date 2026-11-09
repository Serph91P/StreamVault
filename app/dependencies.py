import logging
from dataclasses import dataclass
from functools import partial
from inspect import isawaitable
from collections.abc import AsyncIterator, Callable
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database import SessionLocal, database_lifecycle
from app.bootstrap.settings import resolve_app_settings
from app.services.communication.websocket_manager import (
    ConnectionManager,
    websocket_manager,
)
from app.services.core.auth_service import AuthService, AuthTokenError
from app.services.core.settings_service import SettingsService
from app.services.notification_service import NotificationService
from app.services.background_queue_service import (
    BackgroundQueueService,
    background_queue_service,
)

logger = logging.getLogger("streamvault")
event_registry = None
recording_manager = None


def get_lifespan_service(app: FastAPI, provider: Callable):
    """Resolve a factory-provided service without invoking it eagerly."""
    if provider in app.dependency_overrides:
        return app.dependency_overrides[provider]
    if provider is get_recording_manager and not getattr(
        app.state, "legacy_default", True
    ):
        return partial(_get_application_recording_manager, app)
    if provider is get_event_registry and hasattr(app.state, "event_registry_lock"):
        return partial(_initialize_application_event_registry, app)
    return provider


@dataclass(frozen=True)
class AuthIdentity:
    subject: str
    roles: frozenset[str]
    scopes: frozenset[str]
    auth_method: str
    interactive: bool


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    is_admin: bool
    is_active: bool


def get_db(request: Request) -> Generator[Session, None, None]:
    lifecycle = getattr(request.app.state, "database_lifecycle", database_lifecycle)
    db = (
        SessionLocal()
        if lifecycle is database_lifecycle
        else lifecycle.sync_session_factory()
    )
    try:
        yield db
    finally:
        db.close()


async def get_async_db(request: Request) -> AsyncIterator[AsyncSession]:
    lifecycle = getattr(request.app.state, "database_lifecycle", database_lifecycle)
    async with lifecycle.async_session_factory() as session:
        yield session


def get_application_session_factory(
    connection: HTTPConnection,
) -> Callable[[], Session]:
    lifecycle = getattr(connection.app.state, "database_lifecycle", database_lifecycle)
    return (
        SessionLocal
        if lifecycle is database_lifecycle
        else lifecycle.sync_session_factory
    )


def get_auth_service(
    request: Request, db: Session = Depends(get_db, scope="function")
) -> AuthService:
    return AuthService(db=db, settings=resolve_app_settings(request.app))


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:] if header.startswith("Bearer ") else None


def get_current_identity(
    request: Request,
    session_factory: Callable[[], Session] = Depends(get_application_session_factory),
) -> AuthIdentity:
    cached = getattr(request.state, "auth_identity", None)
    if cached:
        return cached
    with session_factory() as db:
        service = AuthService(db=db, settings=resolve_app_settings(request.app))
        token = request.cookies.get("access_token") or _bearer(request)
        if token:
            try:
                _user, claims = service.resolve_access_token(token)
                return AuthIdentity(
                    subject=claims["sub"],
                    roles=frozenset(claims.get("roles", [])),
                    scopes=frozenset(claims.get("scp", [])),
                    auth_method="jwt",
                    interactive=True,
                )
            except AuthTokenError:
                pass
        legacy = request.cookies.get("session") or _bearer(request)
        if legacy:
            user = service.resolve_legacy_session(legacy)
            if user:
                return AuthIdentity(
                    str(user.id),
                    frozenset({"admin"}) if user.is_admin else frozenset(),
                    service._user_scopes(user),
                    "legacy-session",
                    True,
                )
    raise HTTPException(status_code=401, detail="Authentication required")


def require_scopes(*required: str):
    def dependency(
        identity: AuthIdentity = Depends(get_current_identity),
    ) -> AuthIdentity:
        if not set(required).issubset(identity.scopes):
            raise HTTPException(status_code=403, detail="Insufficient scope")
        return identity

    return dependency


def require_interactive_identity(
    identity: AuthIdentity = Depends(get_current_identity),
) -> AuthIdentity:
    if not identity.interactive:
        raise HTTPException(
            status_code=403, detail="Interactive authentication required"
        )
    return identity


def get_current_user(
    identity: AuthIdentity = Depends(get_current_identity),
    session_factory: Callable[[], Session] = Depends(get_application_session_factory),
) -> AuthenticatedUser:
    from app.models import User

    with session_factory() as db:
        user = (
            db.query(User).filter_by(id=int(identity.subject), is_active=True).first()
        )
        if not user:
            raise HTTPException(status_code=403, detail="Access denied")
        return AuthenticatedUser(user.id, user.username, user.is_admin, user.is_active)


def require_admin_user(
    user=Depends(get_current_user),
    identity: AuthIdentity = Depends(get_current_identity),
):
    if not user.is_admin or "admin" not in identity.scopes:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_event_registry():
    global event_registry
    if not event_registry:
        from app.config.settings import get_settings
        from app.events.handler_registry import EventHandlerRegistry

        event_registry = EventHandlerRegistry(
            connection_manager=websocket_manager, settings=get_settings()
        )
        await event_registry.initialize_eventsub()
    return event_registry


def get_recording_manager():
    """Return the process-scoped recording lifecycle facade.

    The manager owns one compatible recording service instance. Its process
    dictionaries are local caches; durable ownership stays in the coordinator.
    """
    global recording_manager
    if recording_manager is None:
        from app.services.recording.recording_manager import RecordingManager

        recording_manager = RecordingManager()
    return recording_manager


def _get_application_recording_manager(app: FastAPI):
    """Build once in the synchronous provider worker, never during create_app."""
    with app.state.recording_manager_lock:
        if app.state.recording_manager is None:
            from app.services.recording.recording_orchestrator import (
                RecordingOrchestrator,
            )
            from app.services.recording.recording_service import RecordingService
            from app.services.recording.recording_manager import RecordingManager

            database = app.state.database_lifecycle
            orchestrator = RecordingOrchestrator(
                settings=resolve_app_settings(app),
                session_factory=database.sync_session_factory,
                connection_manager=app.state.websocket_manager,
                queue_service=app.state.background_queue_service,
            )
            orchestrator.process_manager.proxy_health_service = (
                _get_application_proxy_health_service(app)
            )
            orchestrator.process_manager.twitch_token_service = (
                _get_application_twitch_token_service(app)
            )
            orchestrator.process_manager.streamlink_config_directory = (
                _get_application_streamlink_config_service(app).config_dir
            )
            app.state.recording_manager = RecordingManager(
                service=RecordingService(orchestrator=orchestrator),
                upstream_coordinator=orchestrator.process_manager.upstream_coordinator,
            )
        return app.state.recording_manager


def get_application_recording_manager(connection: HTTPConnection):
    """Synchronous HTTP/WebSocket adapter sharing the lifespan's owned facade."""
    return get_lifespan_service(connection.app, get_recording_manager)()


def _get_application_twitch_api(app: FastAPI):
    with app.state.twitch_api_lock:
        if app.state.twitch_api is None:
            from app.services.api.twitch_api import TwitchAPIService

            app.state.twitch_api = TwitchAPIService(settings=resolve_app_settings(app))
        return app.state.twitch_api


def get_application_twitch_api(connection: HTTPConnection):
    """Resolve a lazy app-owned HTTP pool in the synchronous adapter worker."""
    return _get_application_twitch_api(connection.app)


def _get_application_twitch_token_service(app: FastAPI):
    from app.services.system.twitch_token_service import TwitchTokenService

    with app.state.twitch_token_service_lock:
        service: TwitchTokenService | None = app.state.twitch_token_service
        if service is None:
            service = TwitchTokenService(
                session_factory=app.state.database_lifecycle.sync_session_factory,
                settings=resolve_app_settings(app),
                notify_expiry=_get_application_notification_service(
                    app
                ).send_notification,
            )
            app.state.twitch_token_service = service
        return service


def get_application_twitch_token_service(connection: HTTPConnection):
    return _get_application_twitch_token_service(connection.app)


def get_application_twitch_oauth_service(connection: HTTPConnection):
    from app.services.api.twitch_oauth_service import TwitchOAuthService

    app = connection.app
    with app.state.twitch_oauth_service_lock:
        if app.state.twitch_oauth_service is None:
            app.state.twitch_oauth_service = TwitchOAuthService(
                settings=resolve_app_settings(app),
                twitch_api=_get_application_twitch_api(app),
            )
        return app.state.twitch_oauth_service


def _get_application_live_streaming_service(app: FastAPI):
    from app.services.live_streaming_service import LiveStreamingService

    with app.state.live_streaming_service_lock:
        if app.state.live_streaming_service is None:
            manager = (
                get_recording_manager()
                if getattr(app.state, "legacy_default", False)
                else _get_application_recording_manager(app)
            )
            app.state.live_streaming_service = LiveStreamingService(
                coordinator=manager._upstream_coordinator,
                session_factory=app.state.database_lifecycle.sync_session_factory,
                settings=resolve_app_settings(app),
                token_service=_get_application_twitch_token_service(app),
                proxy_service=_get_application_proxy_health_service(app),
                config_path=str(
                    _get_application_streamlink_config_service(app).twitch_config_path
                ),
            )
        return app.state.live_streaming_service


def _get_application_streamlink_config_service(app: FastAPI):
    from pathlib import Path
    from app.services.system.streamlink_config_service import StreamlinkConfigService

    with app.state.streamlink_config_service_lock:
        if app.state.streamlink_config_service is None:
            app.state.streamlink_config_service = StreamlinkConfigService(
                config_dir=Path(resolve_app_settings(app).BASE_DIR)
                / "config"
                / "streamlink",
                session_factory=app.state.database_lifecycle.sync_session_factory,
            )
        return app.state.streamlink_config_service


def get_streamlink_config_service(connection: HTTPConnection):
    if not hasattr(connection.app.state, "streamlink_config_service_lock"):
        from app.services.system.streamlink_config_service import (
            streamlink_config_service,
        )

        return streamlink_config_service
    return _get_application_streamlink_config_service(connection.app)


def _get_application_recovery_service(app: FastAPI):
    with app.state.unified_recovery_lock:
        if app.state.unified_recovery_service is None:
            from app.services.recording.unified_recovery_service import (
                UnifiedRecoveryService,
            )

            app.state.unified_recovery_service = UnifiedRecoveryService(
                session_factory=app.state.database_lifecycle.sync_session_factory,
                settings=resolve_app_settings(app),
                recording_manager=get_lifespan_service(app, get_recording_manager)(),
                queue_service=app.state.background_queue_service,
                twitch_api=_get_application_twitch_api(app),
            )
        return app.state.unified_recovery_service


def get_application_recovery_service(connection: HTTPConnection):
    return _get_application_recovery_service(connection.app)


def _get_application_event_registry(app: FastAPI):
    with app.state.event_registry_lock:
        if app.state.event_registry is None:
            from app.events.handler_registry import EventHandlerRegistry

            app.state.event_registry = EventHandlerRegistry(
                connection_manager=app.state.websocket_manager,
                settings=resolve_app_settings(app),
                session_factory=app.state.database_lifecycle.sync_session_factory,
                recording_manager=get_lifespan_service(app, get_recording_manager)(),
                notification_service=_get_application_notification_service(app),
                twitch_api=_get_application_twitch_api(app),
                image_service=_get_application_image_service(app),
            )
        return app.state.event_registry


async def _initialize_application_event_registry(app: FastAPI):
    from app.utils.async_db_utils import run_in_thread_pool

    registry = await run_in_thread_pool(_get_application_event_registry, app)
    await registry.initialize_eventsub()
    return registry


async def get_application_event_registry(connection: HTTPConnection):
    result = get_lifespan_service(connection.app, get_event_registry)()
    return await result if isawaitable(result) else result


def get_streamer_service(
    connection: HTTPConnection,
    event_registry=Depends(get_application_event_registry),
):
    from app.services.streamer_service import StreamerService

    return StreamerService(
        session_factory=get_application_session_factory(connection),
        websocket_manager=get_websocket_manager(connection),
        event_registry=event_registry,
        twitch_api=_get_application_twitch_api(connection.app),
        image_service=_get_application_image_service(connection.app),
    )


def get_settings_service(
    db: Session = Depends(get_db),
) -> SettingsService:
    """Yield an overrideable `SettingsService` bound to the DI session.

    The session comes from ``get_db`` (an overrideable seam), so both the
    settings service and its session can be replaced in tests. No direct
    ``SessionLocal()`` construction happens inside the settings router.
    """
    return SettingsService(db)


def get_notification_service() -> NotificationService:
    return NotificationService(websocket_manager=websocket_manager)


def _get_application_notification_service(app: FastAPI) -> NotificationService:
    with app.state.notification_service_lock:
        service: NotificationService | None = app.state.notification_service
        if service is None:
            database = app.state.database_lifecycle
            service = NotificationService(
                websocket_manager=app.state.websocket_manager,
                session_factory=lambda: database.sync_session_factory(),
                settings=resolve_app_settings(app),
            )
            app.state.notification_service = service
        return service


def get_notification_service_factory(
    connection: HTTPConnection,
) -> Callable[[], NotificationService]:
    """Expose notification construction as a lazy, overrideable adapter seam."""
    return partial(_get_application_notification_service, connection.app)


def get_websocket_manager(connection: HTTPConnection) -> ConnectionManager:
    """Resolve the manager at the HTTP/WebSocket adapter boundary."""
    manager: ConnectionManager = getattr(
        connection.app.state, "websocket_manager", websocket_manager
    )
    return manager


def _get_application_image_service(app: FastAPI):
    with app.state.image_service_lock:
        if app.state.image_service is None:
            from app.services.unified_image_service import UnifiedImageService

            app.state.image_service = UnifiedImageService(
                settings=resolve_app_settings(app),
                session_factory=app.state.database_lifecycle.sync_session_factory,
            )
        return app.state.image_service


def get_image_service(connection: HTTPConnection):
    """Overrideable image facade sharing the application's catalogue owner."""
    return _get_application_image_service(connection.app)


def _get_application_image_sync_service(app: FastAPI):
    with app.state.image_sync_service_lock:
        if app.state.image_sync_service is None:
            from app.services.images.image_sync_service import ImageSyncService

            app.state.image_sync_service = ImageSyncService(
                image_service=_get_application_image_service(app),
                session_factory=app.state.database_lifecycle.sync_session_factory,
            )
        return app.state.image_sync_service


def get_image_sync_service(connection: HTTPConnection):
    return _get_application_image_sync_service(connection.app)


def _get_application_auto_image_sync_service(app: FastAPI):
    with app.state.auto_image_sync_service_lock:
        if app.state.auto_image_sync_service is None:
            from app.services.images.auto_image_sync_service import AutoImageSyncService

            app.state.auto_image_sync_service = AutoImageSyncService(
                image_service=_get_application_image_service(app),
                session_factory=app.state.database_lifecycle.sync_session_factory,
            )
        return app.state.auto_image_sync_service


def _get_application_image_refresh_service(app: FastAPI):
    from app.services.images.image_refresh_service import ImageRefreshService

    return ImageRefreshService(
        image_service=_get_application_image_service(app),
        session_factory=app.state.database_lifecycle.sync_session_factory,
    )


def get_image_refresh_service(connection: HTTPConnection):
    return _get_application_image_refresh_service(connection.app)


def _get_application_image_migration_service(app: FastAPI):
    from app.services.migration.image_migration_service import ImageMigrationService

    return ImageMigrationService(
        settings=resolve_app_settings(app),
        session_factory=app.state.database_lifecycle.sync_session_factory,
    )


def get_image_migration_service(connection: HTTPConnection):
    return _get_application_image_migration_service(connection.app)


def _get_application_proxy_health_service(app: FastAPI):
    with app.state.proxy_health_service_lock:
        if app.state.proxy_health_service is None:
            from app.services.proxy.proxy_health_service import ProxyHealthService

            app.state.proxy_health_service = ProxyHealthService(
                settings=resolve_app_settings(app),
                session_factory=app.state.database_lifecycle.sync_session_factory,
                websocket_manager=app.state.websocket_manager,
            )
        return app.state.proxy_health_service


def get_proxy_health_service(connection: HTTPConnection):
    return _get_application_proxy_health_service(connection.app)


def get_background_queue_service(connection: HTTPConnection) -> BackgroundQueueService:
    queue: BackgroundQueueService = getattr(
        connection.app.state, "background_queue_service", background_queue_service
    )
    return queue


async def get_category_service(db: AsyncSession = Depends(get_async_db)):
    """Provide the async category service on a request-scoped session."""
    from app.services.categories.category_service import CategoryService
    from app.services.categories.category_service import CategoryRepository

    return CategoryService(CategoryRepository(db))


def get_video_catalog_service(db: Session = Depends(get_db)):
    """Overrideable provider for the media/video catalog service."""
    from app.services.media.video_catalog_service import VideoCatalogService

    return VideoCatalogService(db=db)
