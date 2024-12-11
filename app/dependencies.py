from fastapi import Depends
from app.database import SessionLocal
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.config.settings import settings
from twitchAPI.twitch import Twitch

# Initialize Twitch client
async def get_twitch():
    twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
    await twitch.authenticate_app([])
    return twitch

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_event_registry():
    return EventHandlerRegistry()

async def get_streamer_service(
    db=Depends(get_db),
    twitch=Depends(get_twitch)
):
    return StreamerService(db=db, twitch=twitch)
