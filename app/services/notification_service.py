import logging
import apprise
from app.models import GlobalSettings
from app.database import SessionLocal
from app.models import GlobalSettings, NotificationSettings


logger = logging.getLogger("streamvault")

class NotificationService:
    def __init__(self):
        self.apprise = apprise.Apprise()
        self._initialize_apprise()

    def _initialize_apprise(self):
        """Initialize Apprise with URLs from database settings"""
        with SessionLocal() as db:
            settings = db.query(GlobalSettings).first()
            if settings and settings.notification_url and settings.notifications_enabled:
                logger.debug(f"Initializing Apprise with URL from database")
                self.apprise.add(settings.notification_url)
                logger.debug("Apprise URL added successfully")
            else:
                logger.debug("Notifications disabled or no URLs configured")

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
            title = ""
            message = ""
            
            if event_type == "online":
                title = f"🟢 {streamer_name} is now live!"
                message = f"Started streaming at {details['started_at']}\nWatch here: {details['url']}"
            elif event_type == "offline":
                title = f"🔴 {streamer_name} went offline"
                message = f"Stream ended at {details.get('ended_at', 'now')}"
            elif event_type == "update":
                title = f"📝 {streamer_name} updated stream information"
                message = f"Title: {details.get('title', '')}\n"
                message += f"Category: {details.get('category_name', '')}"
                if 'url' in details:
                    message += f"\nWatch here: {details['url']}"

            await self.apprise.notify(
                title=title,
                body=message,
                tag=streamer_name
            )
            logger.info("Notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

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
