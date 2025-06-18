from fastapi import APIRouter, Depends, HTTPException
from app.database import SessionLocal, get_db
from app.models import GlobalSettings, NotificationSettings, Stream, Streamer
from app.schemas.settings import GlobalSettingsSchema, StreamerNotificationSettingsSchema, StreamerNotificationSettingsUpdateSchema
from apprise import Apprise
from sqlalchemy.orm import Session, joinedload
import logging
import uuid
from datetime import datetime, timezone
from typing import List
from app.services.notification_service import NotificationService

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/settings",  # This is the correct prefix
    tags=["settings"]
)

def validate_apprise_url(url: str) -> bool:
    try:
        apobj = Apprise()
        return apobj.add(url)
    except Exception:
        return False

def validate_proxy_url(url: str) -> bool:
    """Validate proxy URL format"""
    if not url or not url.strip():
        return True  # Empty URLs are valid (no proxy)
    
    url = url.strip()
    # Check if URL starts with required protocol
    if not url.startswith(('http://', 'https://')):
        return False
    
    return True

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
            notify_online_global=settings.notify_online_global,
            notify_offline_global=settings.notify_offline_global,
            notify_update_global=settings.notify_update_global,
            notify_favorite_category_global=settings.notify_favorite_category_global,
            http_proxy=settings.http_proxy,
            https_proxy=settings.https_proxy,
            apprise_docs_url="https://github.com/caronc/apprise/wiki"
        )

@router.get("/streamer", response_model=List[StreamerNotificationSettingsSchema])
async def get_all_streamer_settings():
    try:
        with SessionLocal() as db:
            settings = db.query(NotificationSettings).join(Streamer).options(
                joinedload(NotificationSettings.streamer)
            ).all()
            return [
                StreamerNotificationSettingsSchema(
                    streamer_id=s.streamer_id,
                    username=s.streamer.username,
                    profile_image_url=s.streamer.profile_image_url,
                    notify_online=s.notify_online,
                    notify_offline=s.notify_offline,
                    notify_update=s.notify_update,
                    notify_favorite_category=s.notify_favorite_category
                )
                for s in settings
            ]
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/streamer/{streamer_id}", response_model=StreamerNotificationSettingsSchema)
async def update_streamer_settings(
    streamer_id: int, 
    settings_data: StreamerNotificationSettingsUpdateSchema
):
    logger.debug(f"Updating settings for streamer {streamer_id}: {settings_data}")
    try:
        with SessionLocal() as db:
            settings = db.query(NotificationSettings).filter_by(streamer_id=streamer_id).first()
            if not settings:
                settings = NotificationSettings(streamer_id=streamer_id)
                db.add(settings)
            
            if settings_data.notify_online is not None:
                settings.notify_online = settings_data.notify_online
            if settings_data.notify_offline is not None:
                settings.notify_offline = settings_data.notify_offline
            if settings_data.notify_update is not None:
                settings.notify_update = settings_data.notify_update
            if settings_data.notify_favorite_category is not None:
                settings.notify_favorite_category = settings_data.notify_favorite_category
            
            db.commit()
            
            streamer = db.query(Streamer).get(streamer_id)
            
            return StreamerNotificationSettingsSchema(
                streamer_id=settings.streamer_id,
                username=streamer.username if streamer else None,
                profile_image_url=streamer.profile_image_url if streamer else None,
                notify_online=settings.notify_online,
                notify_offline=settings.notify_offline,
                notify_update=settings.notify_update,
                notify_favorite_category=settings.notify_favorite_category
            )
    except Exception as e:
        logger.error(f"Error updating streamer settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/streamers")
async def get_streamer_settings():
    try:
        with SessionLocal() as db:
            settings = db.query(NotificationSettings).all()
            return [
                {
                    "streamer_id": s.streamer_id,
                    "notify_online": s.notify_online,
                    "notify_offline": s.notify_offline,
                    "notify_update": s.notify_update,
                    "notify_favorite_category": s.notify_favorite_category
                }
                for s in settings
            ]
    except Exception as e:
        logger.error(f"Error fetching streamer settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch streamer settings")

@router.post("/test-notification")
async def test_notification():
    try:
        with SessionLocal() as db:
            settings = db.query(GlobalSettings).first()
            if not settings:
                raise HTTPException(
                    status_code=400,
                    detail="No settings configured"
                )
            if not settings.notifications_enabled:
                raise HTTPException(
                    status_code=400,
                    detail="Notifications are disabled"
                )
            if not settings.notification_url:
                raise HTTPException(
                    status_code=400,
                    detail="No notification URL configured"
                )

        from app.services.notification_service import NotificationService
        from app.dependencies import websocket_manager
        import uuid
        
        # Generate a unique test ID to track this notification
        test_id = str(uuid.uuid4())
        
        # Send WebSocket notification first
        await websocket_manager.send_notification({
            "type": "channel.update",  # Use channel.update type to match Twitch format
            "data": {
                "test_id": test_id,
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "username": "TestUser",
                "streamer_name": "TestUser",
                "title": "Test Notification",
                "category_name": "StreamVault",
                "message": "This is a test notification from StreamVault."
            }
        })
        
        # Then send external notification via apprise
        notification_service = NotificationService()
        success = await notification_service.send_test_notification()
        
        if success:
            return {"status": "success", "message": "Test notification sent successfully"}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send test notification"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-websocket-notification")
async def test_websocket_notification():
    """Test WebSocket notification delivery to frontend"""
    try:
        from app.dependencies import websocket_manager
        import time
        import uuid
        import random
        
        # Generate unique ID to prevent duplicates
        unique_id = str(uuid.uuid4())
        timestamp = str(int(time.time() * 1000))  # milliseconds timestamp
        
        # Logger adding to help diagnose issues
        logger.info(f"🧪 Sending test WebSocket notification with ID {unique_id}")
        
        # Send a test notification through WebSocket with unique identifiers
        # Note: We need to make sure this type is accepted by the frontend filters
        # Using channel.update to match what would come from Twitch
        test_notification = {
            "type": "channel.update",  # Using channel.update to match Twitch notification type
            "data": {
                "streamer_id": f"test_{unique_id}",
                "twitch_id": f"test_user_{timestamp}",
                "streamer_name": "🧪 Test Notification",
                "username": "🧪 Test Notification", 
                "title": f"Channel Update Test #{timestamp[-4:]}",
                "category_name": "🔧 StreamVault Testing",
                "language": "en",
                "is_live": True,
                "url": "https://twitch.tv/teststreamer",
                "profile_image_url": "https://static-cdn.jtvnw.net/user-default-pictures-uv/de130ab0-def7-11e9-b668-784f43822e80-profile_image-70x70.png",
                "test_id": unique_id,  # Add test identifier
                "timestamp": timestamp,
                "message": f"Twitch channel update - Test #{timestamp[-6:]}"
            }
        }
        
        await websocket_manager.send_notification(test_notification)
        logger.info(f"🧪 Test WebSocket notification sent with ID {unique_id}")
        
        return {
            "status": "success", 
            "message": f"Test WebSocket notification sent successfully (ID: {unique_id[-8:]})",
            "notification_id": unique_id
        }
    except Exception as e:
        logger.error(f"Error sending test WebSocket notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=GlobalSettingsSchema)
async def update_settings(settings_data: GlobalSettingsSchema):
    try:
        with SessionLocal() as db:
            if settings_data.notification_url and not validate_apprise_url(settings_data.notification_url):
                raise HTTPException(status_code=400, detail="Invalid notification URL format")
            
            # Validate proxy URLs
            if settings_data.http_proxy and not validate_proxy_url(settings_data.http_proxy):
                raise HTTPException(status_code=400, detail="HTTP proxy URL must start with 'http://' or 'https://'")
            
            if settings_data.https_proxy and not validate_proxy_url(settings_data.https_proxy):
                raise HTTPException(status_code=400, detail="HTTPS proxy URL must start with 'http://' or 'https://'")
            
            settings = db.query(GlobalSettings).first()
            if not settings:
                settings = GlobalSettings()
                db.add(settings)
            
            settings.notification_url = settings_data.notification_url or ""
            settings.notifications_enabled = settings_data.notifications_enabled
            settings.notify_online_global = settings_data.notify_online_global
            settings.notify_offline_global = settings_data.notify_offline_global
            settings.notify_update_global = settings_data.notify_update_global
            settings.notify_favorite_category_global = settings_data.notify_favorite_category_global
            settings.http_proxy = settings_data.http_proxy or ""
            settings.https_proxy = settings_data.https_proxy or ""
            
            db.commit()
            
            notification_service = NotificationService()
            notification_service._initialize_apprise()
            
            return GlobalSettingsSchema.model_validate(settings)
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
