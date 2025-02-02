from fastapi import APIRouter, Depends, HTTPException
from app.database import SessionLocal, get_db
from app.models import GlobalSettings, NotificationSettings
from app.schemas.settings import GlobalSettingsSchema, StreamerNotificationSettingsSchema
from apprise import Apprise
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"]
)

def validate_apprise_url(url: str) -> bool:
    try:
        apobj = Apprise()
        return apobj.add(url)
    except Exception:
        return False

@router.get("", response_model=GlobalSettingsSchema)
async def get_settings():
    with SessionLocal() as db:
        settings = db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            db.add(settings)
            db.commit()
        return GlobalSettingsSchema(
            notification_url=settings.notification_url,
            notifications_enabled=settings.notifications_enabled,
            apprise_docs_url="https://github.com/caronc/apprise/wiki"
        )

@router.post("", response_model=GlobalSettingsSchema)
async def update_settings(settings_data: GlobalSettingsSchema, db: Session = Depends(get_db)):
    settings = db.query(GlobalSettings).first()
    if not settings:
        settings = GlobalSettings()
        db.add(settings)
    
    if settings_data.notification_url:
        if not validate_apprise_url(settings_data.notification_url):
            raise HTTPException(status_code=400, detail="Invalid notification URL format")
        settings.notification_url = settings_data.notification_url
    
    settings.notifications_enabled = settings_data.notifications_enabled
    db.commit()
    return GlobalSettingsSchema.model_validate(settings)

@router.get("/streamer/{streamer_id}", response_model=StreamerNotificationSettingsSchema)
async def get_streamer_settings(streamer_id: int):
    with SessionLocal() as db:
        settings = db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        return StreamerNotificationSettingsSchema.model_validate(settings)

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
        return StreamerNotificationSettingsSchema.model_validate(settings)