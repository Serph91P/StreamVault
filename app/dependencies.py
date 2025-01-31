import logging
from fastapi import Depends
from app.database import SessionLocal
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.config.settings import settings
from app.services.websocket_manager import ConnectionManager
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from app.services.auth_service import AuthService
from app.services.settings_service import SettingsService

logger = logging.getLogger('streamvault')

# Shared instances
websocket_manager = ConnectionManager()
twitch = None
event_registry = None

# Initialize Twitch client
async def get_twitch():
    global twitch
    if not twitch:
        logger.debug("Initializing Twitch client")
        twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        await twitch.authenticate_app([])
        async for user in twitch.get_users(logins=['twitch']):
            logger.debug(f"Test API call successful: {user.display_name}")
            break
        logger.info("Twitch client initialized and tested successfully")
    return twitch

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_auth_service(db=Depends(get_db)):
    return AuthService(db=db)

async def get_event_registry():
    global event_registry, twitch
    if not event_registry:
        logger.debug("Initializing event registry")
        twitch = await get_twitch()
        logger.debug(f"Twitch client initialized: {twitch}")
        event_registry = EventHandlerRegistry(connection_manager=websocket_manager, twitch=twitch, settings=settings)
        await event_registry.initialize_eventsub()
        logger.debug("Event registry initialization complete")
    return event_registry

def get_streamer_service(
    db=Depends(get_db), 
    twitch_client=Depends(get_twitch)
):
    return StreamerService(db=db, twitch=twitch_client, websocket_manager=websocket_manager)



def get_settings_service():
    db = SessionLocal()
    try:
        yield SettingsService(db)
    finally:
        db.close()
