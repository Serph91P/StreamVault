from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.schemas.settings import (
    GlobalSettingsSchema,
    StreamerNotificationSettingsSchema,
    StreamerNotificationSettingsUpdateSchema,
)
from app.dependencies import (
    get_db,
    get_image_service,
    get_notification_service_factory,
    get_settings_service,
    get_websocket_manager,
    require_scopes,
)
from app.services.core.settings_service import SettingsService
from app.services.notification_service import NotificationService
import logging
from datetime import datetime, timezone
from collections.abc import Callable
from typing import List

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/settings", tags=["settings"]
)  # This is the correct prefix


@router.get("", response_model=GlobalSettingsSchema)
async def get_settings(
    settings_service: SettingsService = Depends(get_settings_service),
):
    return settings_service.get_global_settings_schema()


@router.get("/streamer", response_model=List[StreamerNotificationSettingsSchema])
async def get_all_streamer_settings(
    settings_service: SettingsService = Depends(get_settings_service),
    image_service=Depends(get_image_service),
):
    try:
        return settings_service.get_all_streamer_notification_settings(image_service)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/streamer/{streamer_id}", response_model=StreamerNotificationSettingsSchema
)
async def update_streamer_settings(
    streamer_id: int,
    settings_data: StreamerNotificationSettingsUpdateSchema,
    settings_service: SettingsService = Depends(get_settings_service),
    image_service=Depends(get_image_service),
    _identity=Depends(require_scopes("admin")),
):
    logger.debug(f"Updating settings for streamer {streamer_id}: {settings_data}")
    try:
        return settings_service.update_streamer_notification_settings(
            streamer_id, settings_data, image_service
        )
    except Exception as e:
        logger.error(f"Error updating streamer settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/streamers")
async def get_streamer_settings(
    settings_service: SettingsService = Depends(get_settings_service),
):
    try:
        return settings_service.get_streamer_settings_flat()
    except Exception as e:
        logger.error(f"Error fetching streamer settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch streamer settings")


@router.post("/test-notification")
async def test_notification(
    settings_service: SettingsService = Depends(get_settings_service),
    notification_service_factory: Callable[[], NotificationService] = Depends(
        get_notification_service_factory
    ),
    websocket_manager=Depends(get_websocket_manager),
    _identity=Depends(require_scopes("admin")),
):
    try:
        settings = settings_service.get_global_settings_row()
        if not settings:
            raise HTTPException(status_code=400, detail="No settings configured")
        if not settings.notifications_enabled:
            raise HTTPException(status_code=400, detail="Notifications are disabled")
        if not settings.notification_url:
            raise HTTPException(
                status_code=400, detail="No notification URL configured"
            )

        import uuid

        # Generate a unique test ID to track this notification
        test_id = str(uuid.uuid4())

        # Send WebSocket notification first
        await websocket_manager.send_notification(
            {
                "type": "channel.update",  # Use channel.update type to match Twitch format
                "data": {
                    "test_id": test_id,
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "username": "TestUser",
                    "streamer_name": "TestUser",
                    "title": "Test Notification",
                    "category_name": "StreamVault",
                    "message": "This is a test notification from StreamVault.",
                },
            }
        )

        # Then send external notification via apprise
        notification_service = notification_service_factory()
        success = await notification_service.send_test_notification()

        if success:
            return {
                "status": "success",
                "message": "Test notification sent successfully",
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to send test notification"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test-websocket-notification")
async def test_websocket_notification(
    websocket_manager=Depends(get_websocket_manager),
    _identity=Depends(require_scopes("admin")),
):
    """Test WebSocket notification delivery to frontend"""
    try:
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
                "message": f"Twitch channel update - Test #{timestamp[-6:]}",
            },
        }

        await websocket_manager.send_notification(test_notification)
        logger.info(f"🧪 Test WebSocket notification sent with ID {unique_id}")

        return {
            "status": "success",
            "message": f"Test WebSocket notification sent successfully (ID: {unique_id[-8:]})",
            "notification_id": unique_id,
        }
    except Exception as e:
        logger.error(f"Error sending test WebSocket notification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=GlobalSettingsSchema)
async def update_settings(
    settings_data: GlobalSettingsSchema,
    settings_service: SettingsService = Depends(get_settings_service),
    notification_service_factory: Callable[[], NotificationService] = Depends(
        get_notification_service_factory
    ),
    _identity=Depends(require_scopes("admin")),
):
    try:
        if settings_data.notification_url and not settings_service.validate_apprise_url(
            settings_data.notification_url
        ):
            raise HTTPException(
                status_code=400, detail="Invalid notification URL format"
            )

        # Validate proxy URLs
        if settings_data.http_proxy and not settings_service.validate_proxy_url(
            settings_data.http_proxy
        ):
            raise HTTPException(
                status_code=400,
                detail="HTTP proxy URL must start with 'http://' or 'https://'",
            )

        if settings_data.https_proxy and not settings_service.validate_proxy_url(
            settings_data.https_proxy
        ):
            raise HTTPException(
                status_code=400,
                detail="HTTPS proxy URL must start with 'http://' or 'https://'",
            )

        settings = settings_service.get_global_settings_row()

        proxy_changed = (
            settings_data.http_proxy != settings.http_proxy
            or settings_data.https_proxy != settings.https_proxy
        )
        codec_changed = (
            hasattr(settings_data, "supported_codecs")
            and settings_data.supported_codecs != settings.supported_codecs
        )
        updated_settings = settings_service.update_global_settings(settings_data)

        notification_service = notification_service_factory()
        notification_service._initialize_apprise()

        # Regenerate Streamlink config after the updated settings are committed.
        try:
            from app.services.system.streamlink_config_service import (
                streamlink_config_service,
            )

            if proxy_changed or codec_changed:
                logger.info(
                    "🔄 Proxy or codec settings changed - regenerating Streamlink config..."
                )
                config_updated = await streamlink_config_service.regenerate_config()

                if config_updated:
                    logger.info("✅ Streamlink config updated with new settings")
                else:
                    logger.warning(
                        "⚠️ Failed to update Streamlink config - recordings may use old settings"
                    )
        except Exception as config_error:
            logger.error(f"❌ Error regenerating Streamlink config: {config_error}")
            # Don't fail the whole settings update if config regeneration fails

        return updated_settings
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/quality-options")
async def get_quality_options(db: Session = Depends(get_db)):
    """
    Get available quality options based on OAuth token configuration.

    Returns quality options with enabled/disabled status based on whether
    a database or environment Twitch token is configured. 1440p requires
    OAuth authentication.
    """
    try:
        from app.services.system.streamlink_config_service import (
            streamlink_config_service,
        )
        from app.services.system.twitch_token_service import TwitchTokenService

        token_service = TwitchTokenService(db)
        has_oauth = bool(await token_service.get_valid_access_token())

        # Get quality options with availability info
        qualities = streamlink_config_service.get_available_qualities(has_oauth)

        return {
            "qualities": qualities,
            "oauth_configured": has_oauth,
            "message": "H.265/1440p available"
            if has_oauth
            else "Save a Twitch OAuth token for H.265/1440p access",
        }
    except Exception as e:
        logger.error(f"Error getting quality options: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/codec-options")
async def get_codec_options(db: Session = Depends(get_db)):
    """
    Get available codec options with OAuth authentication requirements.

    Returns codec options with enabled/disabled status based on OAuth token.
    H.265/HEVC and AV1 require OAuth authentication on Twitch.
    """
    try:
        from app.services.system.twitch_token_service import TwitchTokenService

        token_service = TwitchTokenService(db)
        has_oauth = bool(await token_service.get_valid_access_token())

        codecs = [
            {
                "value": "av1,h265,h264",
                "label": "All Codecs (AV1 > H.265 > H.264)",
                "description": "Best quality - tries AV1 first, falls back to H.265, then H.264",
                "enabled": has_oauth,
                "requires_oauth": True,
                "tooltip": (
                    "Requires OAuth authentication for AV1/H.265 access"
                    if not has_oauth
                    else "Highest quality available"
                ),
            },
            {
                "value": "h265,h264",
                "label": "H.265 + H.264",
                "description": "Good quality - tries H.265/HEVC first, falls back to H.264",
                "enabled": has_oauth,
                "requires_oauth": True,
                "tooltip": (
                    "Requires OAuth authentication for H.265 access"
                    if not has_oauth
                    else "Better quality than H.264 only"
                ),
            },
            {
                "value": "h264",
                "label": "H.264 Only (No Auth Required)",
                "description": "Standard quality - works without OAuth token",
                "enabled": True,
                "requires_oauth": False,
                "tooltip": "Available to all users (no authentication needed)",
            },
        ]

        return {
            "codecs": codecs,
            "oauth_configured": has_oauth,
            "message": "H.265/AV1 codecs available"
            if has_oauth
            else "Save a Twitch OAuth token for H.265/AV1 codecs",
            "note": "Codec availability depends on streamer's broadcast settings and Twitch's transcoding",
        }
    except Exception as e:
        logger.error(f"Error getting codec options: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
