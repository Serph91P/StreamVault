from fastapi import APIRouter, Depends, HTTPException
from app.database import SessionLocal
from app.models import GlobalSettings, NotificationSettings
from apprise import Apprise
from typing import Dict, Any

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

@router.post("")
async def update_settings(settings_data: dict):
    if settings_data.get("notification_url") and not validate_apprise_url(settings_data["notification_url"]):
        raise HTTPException(status_code=400, detail="Invalid notification URL format")

    with SessionLocal() as db:
        settings = db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            db.add(settings)
        
        settings.notification_url = settings_data.get("notification_url")
        settings.notifications_enabled = settings_data.get("notifications_enabled", True)
        db.commit()
        return settings

@router.get("/streamer/{streamer_id}")
async def get_streamer_settings(streamer_id: int):
    with SessionLocal() as db:
        settings = db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        return settings

@router.post("/streamer/{streamer_id}")
async def update_streamer_settings(streamer_id: int, settings_data: dict):
    with SessionLocal() as db:
        settings = db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            db.add(settings)
        
        settings.notify_online = settings_data.get("notify_online", True)
        settings.notify_offline = settings_data.get("notify_offline", True)
        settings.notify_update = settings_data.get("notify_update", True)
        db.commit()
        return settings