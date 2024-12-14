from fastapi import Depends
from app.database import SessionLocal
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.config.settings import settings
from app.services.websocket_manager import ConnectionManager
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook

# Shared instances
manager = ConnectionManager()
twitch = None
websocket_manager = ConnectionManager()
event_registry = EventHandlerRegistry(connection_manager=websocket_manager)

# Initialize Twitch client
async def get_twitch():
    global twitch
    if not twitch:
        twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        await twitch.authenticate_app([])
    return twitch

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_event_registry():
    global event_registry, twitch
    if not event_registry:
        twitch = await get_twitch()  # Make sure to await this
        event_registry = EventHandlerRegistry(connection_manager=websocket_manager, twitch=twitch)
        await event_registry.initialize_eventsub()
    return event_registry
def get_streamer_service(db=Depends(get_db)):
    return StreamerService(db=db, twitch=twitch)