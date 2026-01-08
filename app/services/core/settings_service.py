from sqlalchemy.orm import Session
from app.models import GlobalSettings, NotificationSettings
from app.schemas.settings import GlobalSettingsSchema, StreamerNotificationSettingsSchema
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
            logger.error(f"Failed to validate Apprise URL: {url}", exc_info=True)
            return False

    async def get_settings(self) -> GlobalSettings:
        settings = self.db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            self.db.add(settings)
            self.db.commit()
        return settings

    async def update_settings(self, settings_data: GlobalSettingsSchema) -> GlobalSettings:
        settings = await self.get_settings()
        for key, value in settings_data.dict(exclude_unset=True).items():
            setattr(settings, key, value)
        self.db.commit()
        return settings

    async def get_streamer_settings(self, streamer_id: int) -> StreamerNotificationSettingsSchema:
        settings = self.db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            self.db.add(settings)
            self.db.commit()
        return StreamerNotificationSettingsSchema.model_validate(settings)

    async def update_streamer_settings(
        self,
        streamer_id: int,
        settings_data: StreamerNotificationSettingsSchema
    ) -> StreamerNotificationSettingsSchema:
        settings = self.db.query(NotificationSettings)\
            .filter(NotificationSettings.streamer_id == streamer_id)\
            .first()
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            self.db.add(settings)

        settings.notify_online = settings_data.notify_online
        settings.notify_offline = settings_data.notify_offline
        settings.notify_update = settings_data.notify_update
        self.db.commit()
        return StreamerNotificationSettingsSchema.model_validate(settings)
