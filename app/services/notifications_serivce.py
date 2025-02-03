from apprise import Apprise
from sqlalchemy.orm import Session
from app.models import NotificationSettings, GlobalSettings
import logging

logger = logging.getLogger("streamvault")

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self._apprise = Apprise()
        self._load_settings()

    def _load_settings(self):
        settings = self.db.query(GlobalSettings).first()
        if settings and settings.notification_url and settings.notifications_enabled:
            try:
                self._apprise.add(settings.notification_url)
            except Exception as e:
                logger.error(f"Failed to load notification settings: {e}")

    async def notify(self, streamer_id: int, event_type: str, message: str):
        settings = self.db.query(GlobalSettings).first()
        if not settings or not settings.notifications_enabled:
            return

        notification_settings = self.db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()

        if not notification_settings:
            return

        # Check global settings first, then individual overrides
        should_notify = {
            "stream.online": settings.notify_online_global and notification_settings.notify_online,
            "stream.offline": settings.notify_offline_global and notification_settings.notify_offline,
            "channel.update": settings.notify_update_global and notification_settings.notify_update
        }.get(event_type, False)

        if should_notify:
            try:
                await self._apprise.async_notify(body=message)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")