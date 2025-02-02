from fastapi import APIRouter, Depends, HTTPException, Request
from app.database import SessionLocal, get_db
from app.models import GlobalSettings, NotificationSettings
from apprise import Apprise
from typing import Dict, Any
from sqlalchemy.orm import Session
import logging
from app.schemas.settings import StreamerNotificationSettingsSchema

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)

def validate_apprise_url(url: str) -> bool:
    try:
        apobj = Apprise()
        return apobj.add(url)
    except Exception:
        return False

@router.get("")
async def get_settings():
    with SessionLocal() as db:
        settings = db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            db.add(settings)
            db.commit()
        return {
            "notification_url": settings.notification_url,
            "notifications_enabled": settings.notifications_enabled,
            "apprise_docs_url": "https://github.com/caronc/apprise/wiki"
        }

@router.post("/")
async def update_settings(settings: NotificationSettings, db: Session = Depends(get_db)):
    global_settings = db.query(GlobalSettings).first()
    if not global_settings:
        global_settings = GlobalSettings()
        db.add(global_settings)
    
    if settings.notification_url:
        if validate_apprise_url(settings.notification_url):
            global_settings.notification_url = settings.notification_url
    
    db.commit()
    return settings

@router.get("/streamer/{streamer_id}", response_model=StreamerNotificationSettingsSchema)
async def get_streamer_settings(streamer_id: int):
    with SessionLocal() as db:
        settings = db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        return settings

@router.post("/streamer/{streamer_id}", response_model=StreamerNotificationSettingsSchema)
async def update_streamer_settings(
    streamer_id: int, 
    settings_data: StreamerNotificationSettingsSchema
):
    logger.debug(f"Updating settings for streamer {streamer_id}: {settings_data}")
    with SessionLocal() as db:
        settings = db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            db.add(settings)
        
        settings.notify_online = settings_data.notify_online
        settings.notify_offline = settings_data.notify_offline
        settings.notify_update = settings_data.notify_update
        db.commit()
        return settings