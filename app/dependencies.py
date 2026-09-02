import logging
from dataclasses import dataclass
from collections.abc import Callable
from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.communication.websocket_manager import ConnectionManager
from app.services.core.auth_service import AuthService, AuthTokenError
from app.services.core.settings_service import SettingsService
from app.services.notification_service import NotificationService

logger = logging.getLogger("streamvault")
websocket_manager = ConnectionManager()
event_registry = None
recording_manager = None


@dataclass(frozen=True)
class AuthIdentity:
    subject: str
    roles: frozenset[str]
    scopes: frozenset[str]
    auth_method: str
    interactive: bool


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db=db)


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:] if header.startswith("Bearer ") else None


def get_current_identity(
    request: Request, service: AuthService = Depends(get_auth_service)
) -> AuthIdentity:
    cached = getattr(request.state, "auth_identity", None)
    if cached:
        return cached
    token = request.cookies.get("access_token") or _bearer(request)
    if token:
        try:
            claims = service.decode_access_token(token)
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
    db: Session = Depends(get_db),
):
    from app.models import User

    user = db.query(User).filter_by(id=int(identity.subject), is_active=True).first()
    if not user:
        raise HTTPException(status_code=403, detail="Access denied")
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


def get_streamer_service(
    db: Session = Depends(get_db), event_registry=Depends(get_event_registry)
):
    from app.services.streamer_service import StreamerService

    return StreamerService(
        db=db, websocket_manager=websocket_manager, event_registry=event_registry
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


def get_notification_service_factory() -> Callable[[], NotificationService]:
    """Expose notification construction as a lazy, overrideable adapter seam."""
    return get_notification_service


def get_websocket_manager() -> ConnectionManager:
    """Overrideable adapter for the shared WebSocket manager."""
    return websocket_manager


def get_image_service():
    """Overrideable adapter for the unified image service.

    This is the compatibility facade (``app.services.unified_image_service``).
    Tests may override this dependency to provide a fake adapter so no real
    HTTP/download or filesystem work happens.
    """
    from app.services.unified_image_service import unified_image_service

    return unified_image_service


def get_category_service(db: Session = Depends(get_db)):
    """Overrideable provider for the category domain service."""
    from app.services.categories.category_service import CategoryService
    from app.services.categories.category_service import CategoryRepository

    return CategoryService(CategoryRepository(db))


def get_video_catalog_service(db: Session = Depends(get_db)):
    """Overrideable provider for the media/video catalog service."""
    from app.services.media.video_catalog_service import VideoCatalogService

    return VideoCatalogService(db=db)
