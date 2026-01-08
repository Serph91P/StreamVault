from fastapi import APIRouter, HTTPException
from app.database import SessionLocal
from app.models import GlobalSettings, NotificationSettings, Streamer
from app.schemas.settings import GlobalSettingsSchema, StreamerNotificationSettingsSchema, StreamerNotificationSettingsUpdateSchema
from apprise import Apprise
from sqlalchemy.orm import joinedload
import logging
from datetime import datetime, timezone
from typing import List
from app.services.notification_service import NotificationService
from app.services.unified_image_service import unified_image_service

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
            # System notification settings (Migration 028)
            notify_recording_started=settings.notify_recording_started if hasattr(settings, 'notify_recording_started') else False,
            notify_recording_failed=settings.notify_recording_failed if hasattr(settings, 'notify_recording_failed') else True,
            notify_recording_completed=settings.notify_recording_completed if hasattr(settings, 'notify_recording_completed') else False,
            # Codec preferences (Migration 024)
            supported_codecs=settings.supported_codecs if hasattr(settings, 'supported_codecs') else "h264,h265",
            prefer_higher_quality=settings.prefer_higher_quality if hasattr(settings, 'prefer_higher_quality') else True,
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
                    profile_image_url=unified_image_service.get_profile_image_url(
                        s.streamer.id,
                        s.streamer.profile_image_url
                    ),
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
                profile_image_url=unified_image_service.get_profile_image_url(
                    streamer.id,
                    streamer.profile_image_url
                ) if streamer else None,
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
            # System notification settings (Migration 028)
            settings.notify_recording_started = settings_data.notify_recording_started
            settings.notify_recording_failed = settings_data.notify_recording_failed
            settings.notify_recording_completed = settings_data.notify_recording_completed
            # Codec preferences (Migration 024)
            if hasattr(settings_data, 'supported_codecs'):
                settings.supported_codecs = settings_data.supported_codecs or "h264,h265"
            if hasattr(settings_data, 'prefer_higher_quality'):
                settings.prefer_higher_quality = settings_data.prefer_higher_quality
            settings.http_proxy = settings_data.http_proxy or ""
            settings.https_proxy = settings_data.https_proxy or ""

            db.commit()

            notification_service = NotificationService()
            notification_service._initialize_apprise()

            # Regenerate Streamlink config if proxy or codec settings changed
            try:
                from app.services.system.streamlink_config_service import streamlink_config_service

                # Check if settings that affect Streamlink were changed
                proxy_changed = (
                    settings_data.http_proxy != settings.http_proxy or
                    settings_data.https_proxy != settings.https_proxy
                )
                codec_changed = hasattr(settings_data, 'supported_codecs') and settings_data.supported_codecs != settings.supported_codecs
                
                if proxy_changed or codec_changed:
                    logger.info("🔄 Proxy or codec settings changed - regenerating Streamlink config...")
                    config_updated = await streamlink_config_service.regenerate_config()

                    if config_updated:
                        logger.info("✅ Streamlink config updated with new settings")
                    else:
                        logger.warning("⚠️ Failed to update Streamlink config - recordings may use old settings")
            except Exception as config_error:
                logger.error(f"❌ Error regenerating Streamlink config: {config_error}")
                # Don't fail the whole settings update if config regeneration fails

            return GlobalSettingsSchema.model_validate(settings)
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality-options")
async def get_quality_options():
    """
    Get available quality options based on OAuth token configuration.

    Returns quality options with enabled/disabled status based on whether
    TWITCH_OAUTH_TOKEN is configured. 1440p requires OAuth authentication.
    """
    try:
        from app.config.settings import settings
        from app.services.system.streamlink_config_service import streamlink_config_service

        # Check if OAuth token is configured
        has_oauth = bool(settings.TWITCH_OAUTH_TOKEN and settings.TWITCH_OAUTH_TOKEN.strip())

        # Get quality options with availability info
        qualities = streamlink_config_service.get_available_qualities(has_oauth)

        return {
            "qualities": qualities,
            "oauth_configured": has_oauth,
            "message": "H.265/1440p available" if has_oauth else "Set TWITCH_OAUTH_TOKEN for H.265/1440p access"
        }
    except Exception as e:
        logger.error(f"Error getting quality options: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/codec-options")
async def get_codec_options():
    """
    Get available codec options with OAuth authentication requirements.

    Returns codec options with enabled/disabled status based on OAuth token.
    H.265/HEVC and AV1 require OAuth authentication on Twitch.
    """
    try:
        from app.config.settings import settings

        # Check if OAuth token is configured
        has_oauth = bool(settings.TWITCH_OAUTH_TOKEN and settings.TWITCH_OAUTH_TOKEN.strip())

        codecs = [
            {
                "value": "av1,h265,h264",
                "label": "All Codecs (AV1 > H.265 > H.264)",
                "description": "Best quality - tries AV1 first, falls back to H.265, then H.264",
                "enabled": has_oauth,
                "requires_oauth": True,
                "tooltip": "Requires OAuth authentication for AV1/H.265 access" if not has_oauth else "Highest quality available"
            },
            {
                "value": "h265,h264",
                "label": "H.265 + H.264",
                "description": "Good quality - tries H.265/HEVC first, falls back to H.264",
                "enabled": has_oauth,
                "requires_oauth": True,
                "tooltip": "Requires OAuth authentication for H.265 access" if not has_oauth else "Better quality than H.264 only"
            },
            {
                "value": "h264",
                "label": "H.264 Only (No Auth Required)",
                "description": "Standard quality - works without OAuth token",
                "enabled": True,
                "requires_oauth": False,
                "tooltip": "Available to all users (no authentication needed)"
            }
        ]

        return {
            "codecs": codecs,
            "oauth_configured": has_oauth,
            "message": "H.265/AV1 codecs available" if has_oauth else "Set TWITCH_OAUTH_TOKEN for H.265/AV1 codecs",
            "note": "Codec availability depends on streamer's broadcast settings and Twitch's transcoding"
        }
    except Exception as e:
        logger.error(f"Error getting codec options: {e}")
        raise HTTPException(status_code=500, detail=str(e))
