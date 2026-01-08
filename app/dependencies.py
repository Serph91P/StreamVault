import logging
from fastapi import Depends
from app.database import SessionLocal
from app.config.settings import settings
from app.services.communication.websocket_manager import ConnectionManager
from app.services.core.auth_service import AuthService
from app.services.core.settings_service import SettingsService
from app.services.notification_service import NotificationService

logger = logging.getLogger('streamvault')

# Shared instances
websocket_manager = ConnectionManager()
event_registry = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_service(db=Depends(get_db)):
    return AuthService(db=db)


async def get_event_registry():
    global event_registry
    if not event_registry:
        logger.debug("Initializing event registry")
        from app.events.handler_registry import EventHandlerRegistry
        event_registry = EventHandlerRegistry(
            connection_manager=websocket_manager,
            settings=settings
        )
        await event_registry.initialize_eventsub()
        logger.debug("Event registry initialization complete")
    return event_registry


def get_streamer_service(
    db=Depends(get_db),
    event_registry=Depends(get_event_registry)
):
    from app.services.streamer_service import StreamerService
    return StreamerService(
        db=db,
        websocket_manager=websocket_manager,
        event_registry=event_registry
    )


def get_settings_service():
    db = SessionLocal()
    try:
        yield SettingsService(db)
    finally:
        db.close()


def get_notification_service():
    return NotificationService(websocket_manager=websocket_manager)


def get_current_user(db=Depends(get_db)):
    from app.models import User
    user = db.query(User).filter(User.is_admin.is_(True)).first()
    return user
