import logging
import aiohttp
import asyncio
from typing import Dict, Optional, Any
from app.config.settings import settings as app_settings
from apprise import Apprise, NotifyFormat
from app.models import GlobalSettings, NotificationSettings, Streamer
from app.database import SessionLocal

logger = logging.getLogger("streamvault")

class NotificationService:
    def __init__(self):
        self.apprise = Apprise()
        self._notification_url = None
        self._initialize_apprise()

    def _initialize_apprise(self):
        """Initialize Apprise with the notification URL from settings"""
        try:
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Notifications disabled")
                    return
                
                if not settings.notification_url:
                    logger.debug("No notification URL configured")
                    return

                url = settings.notification_url.strip()
                self._notification_url = url
                self.apprise = Apprise()
                
                # Try to add the URL to Apprise
                if self.apprise.add(url):
                    logger.info(f"Apprise initialized successfully with URL: {url}")
                else:
                    logger.error(f"Failed to initialize Apprise with URL: {url}")
                    self._notification_url = None
                    
        except Exception as e:
            logger.error(f"Error initializing Apprise: {e}")
            self._notification_url = None

    async def send_notification(self, message: str, title: str = "StreamVault Notification") -> bool:
        with SessionLocal() as db:
            settings = db.query(GlobalSettings).first()
            if not settings or not settings.notifications_enabled:
                logger.debug("Notifications are disabled, skipping")
                return False
            if not settings.notification_url:
                logger.debug("No notification URLs configured, skipping")
                return False

        # Refresh URLs before sending
        self._initialize_apprise()
        
        logger.debug(f"Preparing to send notification: {message[:50]}...")
        try:
            result = await self.apprise.async_notify(
                body=message,
                title=title
            )
            if result:
                logger.info("Notification sent successfully")
            else:
                logger.error("Failed to send notification - Apprise returned False")
            return result
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return False

    def _get_service_specific_url(self, base_url: str, twitch_url: str, profile_image: str, streamer_name: str, event_type: str, twitch_id: str = None) -> str:
        """Configure service-specific parameters based on the notification service."""
    
        logger.debug(f"Configuring service-specific URL for {base_url}")
    
        # Get appropriate title based on event type
        title_map = {
            "online": f"{streamer_name} is live!",
            "offline": f"{streamer_name} went offline",
            "update": f"{streamer_name} updated stream info",
            "test": "StreamVault Test Notification"
        }
    
        # Für Notifications immer die Twitch-URL des Profilbilds verwenden statt lokalem Pfad
        twitch_profile_url = None
        if twitch_id:
            # Konstruiere die öffentliche Twitch-Profilbild-URL basierend auf der Twitch-ID
            try:
                # Versuche die Twitch-Profilbild-URL aus dem Twitch API zu holen
                user_info = asyncio.run(self.get_user_info(twitch_id))
                if user_info and user_info.get("profile_image_url"):
                    twitch_profile_url = user_info["profile_image_url"]
                    logger.debug(f"Using Twitch profile image URL: {twitch_profile_url}")
            except Exception as e:
                logger.error(f"Error getting Twitch profile image URL: {e}")
    
        if 'ntfy' in base_url:
            # Ntfy configuration
            params = [
                f"click={twitch_url}",
                f"priority={'high' if event_type == 'online' else 'default'}"
            ]
        
            # Event-spezifische Tags
            if event_type == "online":
                params.append("tags=live_stream,online")
            elif event_type == "offline":
                params.append("tags=stream,offline")
            elif event_type == "update":
                params.append("tags=stream,update")
            else:
                params.append("tags=notification")
        
            # Verwende die Twitch-URL wenn verfügbar, sonst skip
            if twitch_profile_url:
                params.append(f"avatar_url={twitch_profile_url}")
        
            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated ntfy URL: {final_url}")
            return final_url
    
        elif 'discord' in base_url:
            # Discord configuration
            final_url = (f"{base_url}?"
                    f"avatar_url={profile_image if event_type != 'test' else '/app/frontend/public/ms-icon-310x310.png'}&"
                    f"title={title_map.get(event_type, 'StreamVault Notification')}&"
                    f"href={twitch_url}&"
                    f"format=markdown")
            logger.debug(f"Generated discord URL: {final_url}")
            return final_url
            
        elif 'telegram' in base_url or 'tgram' in base_url:
            # Telegram configuration
            params = []
            if profile_image:
                params.append("image=yes")
            params.append("format=markdown")
            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug(f"Generated telegram URL: {final_url}")
            return final_url
    
        elif 'matrix' in base_url:
            # Matrix configuration
            params = [
                "msgtype=text",
                "format=markdown",
                f"thumbnail={'true' if profile_image else 'false'}"
            ]
            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated matrix URL: {final_url}")
            return final_url
    
        elif 'slack' in base_url:
            # Slack configuration
            final_url = (f"{base_url}?"
                    f"footer=yes&"
                    f"image={'yes' if profile_image else 'no'}")
            logger.debug(f"Generated slack URL: {final_url}")
            return final_url
    
        elif 'pover' in base_url:
            # Pushover configuration
            priority = "high" if event_type == "online" else "normal"
            final_url = (f"{base_url}?"
                    f"priority={priority}&"
                    f"url={twitch_url}&"
                    f"url_title=Watch Stream")
            logger.debug(f"Generated pushover URL: {final_url}")
            return final_url
    
        # Default case - return original URL if service not specifically handled
        logger.debug(f"No specific configuration for this service, using base URL: {base_url}")
        return base_url
    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict):
        try:
            logger.debug(f"Starting send_stream_notification for {streamer_name}, event type: {event_type}")
            
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Global notifications disabled")
                    return False

                streamer = db.query(Streamer).filter(Streamer.username == streamer_name).first()
                if not streamer:
                    logger.debug(f"Streamer {streamer_name} not found in database")
                    return False

                # Check if notifications are enabled for this specific event type
                should_send = await self.should_notify(streamer.id, event_type)
                logger.debug(f"Should notify for {streamer_name} - {event_type}: {should_send}")
                
                if not should_send:
                    logger.debug(f"Notifications disabled for {streamer_name} - {event_type}")
                    return False

                # Get service-specific URL configuration
                twitch_url = f"https://twitch.tv/{streamer_name}"
                notification_url = self._get_service_specific_url(
                    base_url=settings.notification_url,
                    twitch_url=twitch_url,
                    profile_image=streamer.profile_image_url or "",
                    streamer_name=streamer_name,
                    event_type=event_type,
                    twitch_id=streamer.twitch_id
                )

                # Create new Apprise instance
                apprise = Apprise()
                if not apprise.add(notification_url):
                    logger.error(f"Failed to initialize notification URL: {notification_url}")
                    return False

                # Format message using existing method
                title, message = self._format_notification_message(
                    streamer_name=streamer_name,
                    event_type=event_type,
                    details=details
                )

                # Send notification
                logger.debug(f"Sending notification with title: {title}, message: {message[:50]}...")
                result = await apprise.async_notify(
                    title=title,
                    body=message,
                    body_format=NotifyFormat.TEXT
                )
        
                if not result:
                    logger.error("Apprise notification failed to send")
            
                logger.debug(f"Notification result: {result}")
                return result

        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
            return False
    async def should_notify(self, streamer_id: int, event_type: str) -> bool:
        with SessionLocal() as db:
            global_settings = db.query(GlobalSettings).first()
            if not global_settings or not global_settings.notifications_enabled:
                logger.debug("Global notifications disabled")
                return False

            # Map event types to settings fields
            setting_map = {
                "online": ("notify_online", "notify_online_global"),
                "offline": ("notify_offline", "notify_offline_global"),
                "update": ("notify_update", "notify_update_global")
            }

            streamer_field, global_field = setting_map.get(event_type, (None, None))
            if not streamer_field or not global_field:
                logger.debug(f"Unknown event type: {event_type}")
                return False
                
            # Wichtig: Debug-Ausgabe der globalen Einstellung
            global_enabled = getattr(global_settings, global_field)
            logger.debug(f"Global setting for {event_type}: {global_enabled}")
            
            if not global_enabled:
                logger.debug(f"Global notifications for {event_type} are disabled")
                return False

            # Streamer-spezifische Einstellungen prüfen
            streamer_settings = db.query(NotificationSettings)\
                .filter(NotificationSettings.streamer_id == streamer_id)\
                .first()

            # Wenn keine streamer-spezifischen Einstellungen existieren, verwende global
            if not streamer_settings:
                logger.debug(f"No specific settings for streamer {streamer_id}, using global: {global_enabled}")
                return global_enabled
                
            # Streamer-spezifische Einstellung holen
            streamer_enabled = getattr(streamer_settings, streamer_field)
            logger.debug(f"Streamer-specific setting for {event_type}: {streamer_enabled}")
            
            # Für diesen Streamer aktiviert?
            return streamer_enabled

    async def send_test_notification(self) -> bool:
        """Send a test notification using current settings"""
        try:
            if not self._notification_url:
                logger.error("No notification URL configured")
                return False

            # Create new Apprise instance for test
            apprise = Apprise()
            if not apprise.add(self._notification_url):
                logger.error(f"Invalid notification URL: {self._notification_url}")
                return False
                
            logger.debug(f"Sending test notification via: {self._notification_url}")
            
            result = await apprise.async_notify(
                title="🔔 StreamVault Test Notification",
                body=(
                    "This is a test notification from StreamVault.\n\n"
                    "If you receive this, your notification settings are working correctly!"
                )
            )
            
            if result:
                logger.info("Test notification sent successfully")
                return True
            
            logger.error("Failed to send test notification")
            return False
                
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False

    def _format_notification_message(self, streamer_name: str, event_type: str, details: dict) -> tuple[str, str]:
        """Format notification message and title based on event type"""
        title = "StreamVault Notification"
        
        if event_type == "online":
            message = (
                f"🟢 {streamer_name} is now live!\n\n"
                f"Started streaming: {details.get('title', 'No title')}\n"
                f"Category: {details.get('category_name', 'No category')}"
            )
        elif event_type == "offline":
            message = f"🔴 {streamer_name} went offline\n\nStream ended"
        elif event_type == "update":
            message = (
                f"📝 {streamer_name} updated stream information\n\n"
                f"New title: {details.get('title', 'No title')}\n"
                f"Category: {details.get('category_name', 'No category')}"
            )
        else:
            message = f"Event notification for {streamer_name}"
        
        return title, message

async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user info from Twitch API including profile image"""
    try:
        # Access-Token von Twitch API holen (vereinfachte Version)
        from app.config.settings import settings as app_settings
        
        async with aiohttp.ClientSession() as session:
            # Zuerst Access Token holen
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": app_settings.TWITCH_APP_ID,
                    "client_secret": app_settings.TWITCH_APP_SECRET,
                    "grant_type": "client_credentials"
                }
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to get access token: {response.status}")
                    return None
                
                data = await response.json()
                access_token = data["access_token"]
            
            # Dann User-Info holen
            async with session.get(
                f"https://api.twitch.tv/helix/users?id={user_id}",
                headers={
                    "Client-ID": app_settings.TWITCH_APP_ID,
                    "Authorization": f"Bearer {access_token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["data"][0] if data.get("data") else None
        return None
    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
        return None
