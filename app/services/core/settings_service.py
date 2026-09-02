from sqlalchemy.orm import Session
from app.models import GlobalSettings, NotificationSettings, Streamer
from app.schemas.settings import (
    GlobalSettingsSchema,
    StreamerNotificationSettingsSchema,
)
from sqlalchemy.orm import joinedload
from apprise import Apprise
import logging

logger = logging.getLogger("streamvault")


class SettingsService:
    """Focused sync seam for the settings router (Phase 4A, issue #826).

    Owns the Sync persistence (via a DI-provided ``Session``) so the settings
    router no longer constructs ``SessionLocal()`` or runs ad-hoc SQL itself.
    """

    def __init__(self, db: Session):
        self.db = db

    def validate_apprise_url(self, url: str) -> bool:
        try:
            apobj = Apprise()
            return apobj.add(url)
        except Exception:
            logger.error("Failed to validate Apprise URL", exc_info=True)
            return False

    @staticmethod
    def validate_proxy_url(url: str) -> bool:
        """Validate proxy URL format (mirrors the router's original helper)."""
        if not url or not url.strip():
            return True  # Empty URLs are valid (no proxy)
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return False
        return True

    async def get_settings(self) -> GlobalSettings:
        settings = self.db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            self.db.add(settings)
            self.db.commit()
        return settings

    def get_global_settings_row(self) -> GlobalSettings:
        settings = self.db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings(id=1)
            self.db.add(settings)
            self.db.commit()
        return settings

    def get_global_settings_schema(self) -> GlobalSettingsSchema:
        settings = self.get_global_settings_row()

        def _bool(value, default: bool) -> bool:
            return default if value is None else bool(value)

        def _str(value, default: str) -> str:
            return default if value is None else str(value)

        def _int(value, default: int) -> int:
            return default if value is None else int(value)

        return GlobalSettingsSchema(
            notification_url=_str(settings.notification_url, ""),
            notifications_enabled=_bool(settings.notifications_enabled, True),
            notify_online_global=_bool(settings.notify_online_global, True),
            notify_offline_global=_bool(settings.notify_offline_global, True),
            notify_update_global=_bool(settings.notify_update_global, True),
            notify_favorite_category_global=_bool(
                settings.notify_favorite_category_global, True
            ),
            # System notification settings (Migration 028)
            notify_recording_started=_bool(
                settings.notify_recording_started
                if hasattr(settings, "notify_recording_started")
                else False,
                False,
            ),
            notify_recording_failed=_bool(
                settings.notify_recording_failed
                if hasattr(settings, "notify_recording_failed")
                else True,
                True,
            ),
            notify_recording_completed=_bool(
                settings.notify_recording_completed
                if hasattr(settings, "notify_recording_completed")
                else False,
                False,
            ),
            # Codec preferences (Migration 024)
            supported_codecs=_str(
                settings.supported_codecs
                if hasattr(settings, "supported_codecs")
                else "h264,h265",
                "h264,h265",
            ),
            prefer_higher_quality=_bool(
                settings.prefer_higher_quality
                if hasattr(settings, "prefer_higher_quality")
                else True,
                True,
            ),
            twitch_max_concurrent_upstreams=_int(
                settings.twitch_max_concurrent_upstreams
                if hasattr(settings, "twitch_max_concurrent_upstreams")
                else 5,
                5,
            ),
            http_proxy=_str(settings.http_proxy, ""),
            https_proxy=_str(settings.https_proxy, ""),
            apprise_docs_url="https://github.com/caronc/apprise/wiki",
        )

    def get_all_streamer_notification_settings(self, image_service=None) -> list:
        """Return all streamer notification settings with resolved images."""
        settings = (
            self.db.query(NotificationSettings)
            .join(Streamer)
            .options(joinedload(NotificationSettings.streamer))
            .all()
        )

        def _profile_image_url(streamer):
            if image_service is None or streamer is None:
                return None
            return image_service.get_profile_image_url(
                streamer.id, streamer.profile_image_url
            )

        return [
            StreamerNotificationSettingsSchema(
                streamer_id=s.streamer_id,
                username=s.streamer.username,
                profile_image_url=_profile_image_url(s.streamer),
                notify_online=s.notify_online,
                notify_offline=s.notify_offline,
                notify_update=s.notify_update,
                notify_favorite_category=s.notify_favorite_category,
            )
            for s in settings
        ]

    def update_streamer_notification_settings(
        self, streamer_id: int, settings_data, image_service=None
    ) -> StreamerNotificationSettingsSchema:
        settings = (
            self.db.query(NotificationSettings)
            .filter_by(streamer_id=streamer_id)
            .first()
        )
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            self.db.add(settings)

        if settings_data.notify_online is not None:
            settings.notify_online = settings_data.notify_online
        if settings_data.notify_offline is not None:
            settings.notify_offline = settings_data.notify_offline
        if settings_data.notify_update is not None:
            settings.notify_update = settings_data.notify_update
        if settings_data.notify_favorite_category is not None:
            settings.notify_favorite_category = settings_data.notify_favorite_category

        self.db.commit()

        streamer = self.db.query(Streamer).get(streamer_id)

        profile_image_url = None
        if streamer is not None and image_service is not None:
            profile_image_url = image_service.get_profile_image_url(
                streamer.id, streamer.profile_image_url
            )

        return StreamerNotificationSettingsSchema(
            streamer_id=settings.streamer_id,
            username=streamer.username if streamer else None,
            profile_image_url=profile_image_url,
            notify_online=settings.notify_online,
            notify_offline=settings.notify_offline,
            notify_update=settings.notify_update,
            notify_favorite_category=settings.notify_favorite_category,
        )

    def get_streamer_settings_flat(self) -> list:
        settings = self.db.query(NotificationSettings).all()
        return [
            {
                "streamer_id": s.streamer_id,
                "notify_online": s.notify_online,
                "notify_offline": s.notify_offline,
                "notify_update": s.notify_update,
                "notify_favorite_category": s.notify_favorite_category,
            }
            for s in settings
        ]

    def update_global_settings(
        self, settings_data: GlobalSettingsSchema
    ) -> GlobalSettingsSchema:
        settings = self.db.query(GlobalSettings).first()
        if not settings:
            settings = GlobalSettings()
            self.db.add(settings)

        settings.notification_url = settings_data.notification_url or ""
        settings.notifications_enabled = settings_data.notifications_enabled
        settings.notify_online_global = settings_data.notify_online_global
        settings.notify_offline_global = settings_data.notify_offline_global
        settings.notify_update_global = settings_data.notify_update_global
        settings.notify_favorite_category_global = (
            settings_data.notify_favorite_category_global
        )
        # System notification settings (Migration 028)
        settings.notify_recording_started = settings_data.notify_recording_started
        settings.notify_recording_failed = settings_data.notify_recording_failed
        settings.notify_recording_completed = settings_data.notify_recording_completed
        # Codec preferences (Migration 024)
        if hasattr(settings_data, "supported_codecs"):
            settings.supported_codecs = settings_data.supported_codecs or "h264,h265"
        if hasattr(settings_data, "prefer_higher_quality"):
            settings.prefer_higher_quality = settings_data.prefer_higher_quality
        settings.twitch_max_concurrent_upstreams = (
            settings_data.twitch_max_concurrent_upstreams
        )
        settings.http_proxy = settings_data.http_proxy or ""
        settings.https_proxy = settings_data.https_proxy or ""

        self.db.commit()
        return GlobalSettingsSchema.model_validate(settings)

    async def update_settings(
        self, settings_data: GlobalSettingsSchema
    ) -> GlobalSettings:
        settings = await self.get_settings()
        for key, value in settings_data.dict(exclude_unset=True).items():
            setattr(settings, key, value)
        self.db.commit()
        return settings

    async def get_streamer_settings(
        self, streamer_id: int
    ) -> StreamerNotificationSettingsSchema:
        settings = (
            self.db.query(NotificationSettings)
            .filter(NotificationSettings.streamer_id == streamer_id)
            .first()
        )
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            self.db.add(settings)
            self.db.commit()
        return StreamerNotificationSettingsSchema.model_validate(settings)

    async def update_streamer_settings(
        self, streamer_id: int, settings_data: StreamerNotificationSettingsSchema
    ) -> StreamerNotificationSettingsSchema:
        settings = (
            self.db.query(NotificationSettings)
            .filter(NotificationSettings.streamer_id == streamer_id)
            .first()
        )
        if not settings:
            settings = NotificationSettings(streamer_id=streamer_id)
            self.db.add(settings)

        settings.notify_online = settings_data.notify_online
        settings.notify_offline = settings_data.notify_offline
        settings.notify_update = settings_data.notify_update
        self.db.commit()
        return StreamerNotificationSettingsSchema.model_validate(settings)
