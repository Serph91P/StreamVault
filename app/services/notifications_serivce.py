from apprise import Apprise
from typing import Optional
from sqlalchemy.orm import Session
from app.models import NotificationSettings, GlobalSettings

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self._apprise = Apprise()
        self._load_settings()

    def _load_settings(self):
        settings = self.db.query(GlobalSettings).first()
        if settings and settings.notification_url:
            self._apprise.add(settings.notification_url)

    async def notify(self, streamer_id: int, event_type: str, message: str):
        settings = self.db.query(GlobalSettings).first()
        if not settings or not settings.notifications_enabled:
            return

        notification_settings = self.db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()

        if not notification_settings:
            return

        should_notify = {
            "stream.online": notification_settings.notify_online,
            "stream.offline": notification_settings.notify_offline,
            "channel.update": notification_settings.notify_update
        }.get(event_type, False)

        if should_notify:
            await self._apprise.async_notify(body=message)