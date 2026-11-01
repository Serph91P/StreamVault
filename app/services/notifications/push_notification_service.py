"""Browser push orchestration with closed owner-scoped catalog snapshots."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import PushSubscription, GlobalSettings, NotificationSettings
from app.services.communication.enhanced_push_service import (
    EnhancedPushService,
    enhanced_push_service,
)
from app.services.communication.webpush_service import WebPushException
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


@dataclass(frozen=True)
class PushTarget:
    id: int
    subscription_data: str


class PushNotificationService:
    """Handles browser push notifications using the owning catalog and transport."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        push_service: EnhancedPushService | None = None,
    ):
        self._session_factory = session_factory
        self.push_service = push_service or enhanced_push_service

    def _should_notify(self, streamer_id: int, event_type: str) -> bool:
        with (self._session_factory or SessionLocal)() as db:
            global_settings = db.query(GlobalSettings).first()
            if not global_settings or not global_settings.notifications_enabled:
                return False
            setting_map = {
                "online": ("notify_online", "notify_online_global"),
                "offline": ("notify_offline", "notify_offline_global"),
                "update": ("notify_update", "notify_update_global"),
                "favorite_category": (
                    "notify_favorite_category",
                    "notify_favorite_category_global",
                ),
            }
            streamer_field, global_field = setting_map.get(event_type, (None, None))
            if not streamer_field or not global_field:
                return False
            global_enabled = bool(getattr(global_settings, global_field))
            if not global_enabled:
                return False
            streamer_settings = (
                db.query(NotificationSettings)
                .filter(NotificationSettings.streamer_id == streamer_id)
                .first()
            )
            if streamer_settings is None:
                return global_enabled
            return bool(getattr(streamer_settings, streamer_field))

    async def should_notify(self, streamer_id: int, event_type: str) -> bool:
        return await run_in_thread_pool(self._should_notify, streamer_id, event_type)

    def _load_targets(self) -> tuple[PushTarget, ...]:
        with (self._session_factory or SessionLocal)() as db:
            rows = db.execute(
                select(PushSubscription.id, PushSubscription.subscription_data).where(
                    PushSubscription.is_active.is_(True)
                )
            )
            return tuple(PushTarget(row.id, row.subscription_data) for row in rows)

    def _deactivate_expired(self, target: PushTarget) -> None:
        with (self._session_factory or SessionLocal)() as db:
            # A subscription refreshed during HTTP is not the rejected snapshot.
            db.execute(
                update(PushSubscription)
                .where(
                    PushSubscription.id == target.id,
                    PushSubscription.subscription_data == target.subscription_data,
                )
                .values(is_active=False)
            )
            db.commit()

    async def send_push_notifications(
        self, streamer_name: str, event_type: str, details: dict
    ):
        """Send to closed subscription snapshots; only confirmed410 expires one."""
        try:
            active_subscriptions = await run_in_thread_pool(self._load_targets)
            if not active_subscriptions:
                return
            streamer_id = details.get("streamer_id")
            stream_id = details.get("stream_id")
            stream_title = details.get("title", "Stream")
            category_name = details.get("category_name", "")
            if not streamer_id:
                return
            if not await self.should_notify(int(streamer_id), event_type):
                return
            successful_sends = 0
            failed_sends = 0
            for subscription in active_subscriptions:
                try:
                    subscription_data = json.loads(subscription.subscription_data)
                    success = False
                    if event_type == "online":
                        success = (
                            await self.push_service.send_stream_online_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id) if stream_id else None,
                                category_name,
                            )
                        )
                    elif event_type == "offline":
                        success = (
                            await self.push_service.send_stream_offline_notification(
                                subscription_data, streamer_name, int(streamer_id)
                            )
                        )
                    elif event_type == "update":
                        success = (
                            await self.push_service.send_stream_update_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                category_name,
                                int(streamer_id),
                            )
                        )
                    elif event_type == "favorite_category":
                        success = (
                            await self.push_service.send_favorite_category_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                category_name,
                                int(streamer_id),
                            )
                        )
                    elif event_type == "recording_started":
                        success = (
                            await self.push_service.send_recording_started_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id) if stream_id else None,
                            )
                        )
                    elif event_type == "recording_finished" and stream_id:
                        success = await self.push_service.send_recording_finished_notification(
                            subscription_data,
                            streamer_name,
                            stream_title,
                            int(streamer_id),
                            int(stream_id),
                            details.get("duration", "Unknown"),
                        )
                    if success:
                        successful_sends += 1
                    else:
                        failed_sends += 1
                except WebPushException as exc:
                    failed_sends += 1
                    if exc.response is not None and exc.response.status == 410:
                        await run_in_thread_pool(self._deactivate_expired, subscription)
                except Exception:
                    failed_sends += 1
                    logger.warning(
                        "Push delivery failed: subscription_id=%s", subscription.id
                    )
            logger.info(
                f"🔔 PUSH_NOTIFICATION_SUMMARY: event={event_type}, successful={successful_sends}, failed={failed_sends}, total={len(active_subscriptions)}"
            )
        except Exception as exc:
            logger.error("Push notification failed (%s)", type(exc).__name__)
