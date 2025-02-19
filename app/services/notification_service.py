import logging
from apprise import Apprise
from app.models import GlobalSettings, NotificationSettings
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
            return result
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return False

    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict):
        try:
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                logger.debug(f"Current notification settings: enabled={settings.notifications_enabled}, url={settings.notification_url}")
            
                if not settings or not settings.notifications_enabled:
                    logger.debug("Notifications are disabled globally")
                    return False

                if settings.notification_url != self._notification_url:
                    logger.debug(f"URL change detected: old={self._notification_url}, new={settings.notification_url}")
                    self.apprise = Apprise()
                    self._notification_url = settings.notification_url
                    add_result = self.apprise.add(self._notification_url)
                    logger.debug(f"Apprise URL add result: {add_result}")
                    if not add_result:
                        logger.error(f"Failed to initialize new notification URL: {self._notification_url}")
                        return False

                title = ""
                message = ""
                if event_type == "online":
                    title = f"🟢 {streamer_name} is now live!"
                    message = f"Started streaming: {details.get('title', 'No title')}\n"
                    message += f"Category: {details.get('category_name', 'No category')}"
                elif event_type == "offline":
                    title = f"🔴 {streamer_name} went offline"
                    message = "Stream ended"
                elif event_type == "update":
                    title = f"📝 {streamer_name} updated stream information"
                    message = f"New title: {details.get('title', 'No title')}\n"
                    message += f"Category: {details.get('category_name', 'No category')}"

                logger.debug(f"Preparing notification - Title: {title}, Message: {message}")
            
                result = await self.apprise.async_notify(
                    title=title,
                    body=message,
                    tag=streamer_name
                )
            
                logger.debug(f"Notification send result: {result}")
            
                if result:
                    logger.info(f"Notification sent successfully for {streamer_name}")
                    return True
                else:
                    logger.error(f"Failed to send notification for {streamer_name}")
                    return False

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return False
    async def should_notify(self, streamer_id: int, event_type: str) -> bool:
        with SessionLocal() as db:
            global_settings = db.query(GlobalSettings).first()
            if not global_settings or not global_settings.notifications_enabled:
                return False

            streamer_settings = db.query(NotificationSettings)\
                .filter(NotificationSettings.streamer_id == streamer_id)\
                .first()

            # Map event types to settings fields
            setting_map = {
                "online": ("notify_online", "notify_online_global"),
                "offline": ("notify_offline", "notify_offline_global"),
                "update": ("notify_update", "notify_update_global")
            }

            streamer_field, global_field = setting_map.get(event_type, (None, None))
            if not streamer_field or not global_field:
                return False

            # If streamer has specific settings, use those, otherwise use global
            if streamer_settings:
                return getattr(streamer_settings, streamer_field)
            return getattr(global_settings, global_field)

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
