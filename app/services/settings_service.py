from sqlalchemy.orm import Session
from app.models import GlobalSettings, NotificationSettings
from apprise import Apprise
import logging

logger = logging.getLogger("streamvault")

class SettingsService:
    def __init__(self, db: Session):
        self.db = db
    
    def validate_apprise_url(self, url: str) -> bool:
        try:
            apobj = Apprise()
            return apobj.add(url)
        except Exception:
            return False

    async def get_settings(self):
        settings = self.db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            self.db.add(settings)
            self.db.commit()
        return {
            "notification_url": settings.notification_url,
            "notifications_enabled": settings.notifications_enabled,
            "apprise_docs_url": "https://github.com/caronc/apprise/wiki"
        }

    async def update_settings(self, settings_data: NotificationSettings):
        global_settings = self.db.query(GlobalSettings).first()
        if not global_settings:
            global_settings = GlobalSettings()
            self.db.add(global_settings)
        
        if settings_data.notification_url:
            if self.validate_apprise_url(settings_data.notification_url):
                global_settings.notification_url = settings_data.notification_url
        
        self.db.commit()
        return settings_data

    async def get_streamer_settings(self, streamer_id: int):
        return self.db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()

    async def update_streamer_settings(self, streamer_id: int, settings_data: dict):
        settings = self.db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            self.db.add(settings)
        
        settings.notify_online = settings_data.get("notify_online", True)
        settings.notify_offline = settings_data.get("notify_offline", True)
        settings.notify_update = settings_data.get("notify_update", True)
        self.db.commit()
        return settings
