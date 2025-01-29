from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
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
async def get_settings(db: Session = Depends(get_db)) -> Dict[str, Any]:
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
async def update_settings(settings: Dict[str, Any], db: Session = Depends(get_db)):
    if settings.get("notification_url") and not validate_apprise_url(settings["notification_url"]):
        raise HTTPException(status_code=400, detail="Invalid notification URL format")

    db_settings = db.query(GlobalSettings).first()
    if not db_settings:
        db_settings = GlobalSettings()
        db.add(db_settings)
    
    db_settings.notification_url = settings.get("notification_url")
    db_settings.notifications_enabled = settings.get("notifications_enabled", True)
    db.commit()
    return db_settings

@router.get("/streamer/{streamer_id}")
async def get_streamer_settings(streamer_id: int, db: Session = Depends(get_db)):
    settings = db.query(NotificationSettings)\
        .filter(NotificationSettings.streamer_id == streamer_id)\
        .first()
    return settings