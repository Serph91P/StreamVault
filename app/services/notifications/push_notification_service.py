"""
PushNotificationService - Browser push notifications

Extracted from notification_service.py God Class
Handles browser push notifications for subscribers.
"""

import json
import logging
from app.models import PushSubscription, GlobalSettings, NotificationSettings
from app.database import SessionLocal
from app.services.communication.enhanced_push_service import enhanced_push_service

logger = logging.getLogger("streamvault")


class PushNotificationService:
    """Handles browser push notifications"""

    def __init__(self):
        self.push_service = enhanced_push_service

    async def should_notify(self, streamer_id: int, event_type: str) -> bool:
        """Check if notifications should be sent for this streamer and event type"""
        with SessionLocal() as db:
            global_settings = db.query(GlobalSettings).first()
            logger.debug(f"Global settings: notifications_enabled={global_settings.notifications_enabled if global_settings else 'None'}")

            if not global_settings or not global_settings.notifications_enabled:
                logger.debug("Global notifications disabled")
                return False

            # Map event types to settings fields
            setting_map = {
                "online": ("notify_online", "notify_online_global"),
                "offline": ("notify_offline", "notify_offline_global"),
                "update": ("notify_update", "notify_update_global"),
                "favorite_category": ("notify_favorite_category", "notify_favorite_category_global")
            }

            streamer_field, global_field = setting_map.get(event_type, (None, None))
            if not streamer_field or not global_field:
                logger.debug(f"Unknown event type: {event_type}")
                return False

            # Debug-Ausgabe der globalen Einstellung
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

    async def send_push_notifications(self, streamer_name: str, event_type: str, details: dict):
        """Send push notifications to all active subscribers"""
        try:
            logger.info(f"🔔 PUSH_NOTIFICATION_ATTEMPT: streamer={streamer_name}, event={event_type}, details={details}")

            with SessionLocal() as db:
                # Get all active push subscriptions
                active_subscriptions = db.query(PushSubscription).filter(
                    PushSubscription.is_active.is_(True)
                ).all()

                logger.info(f"🔔 PUSH_SUBSCRIPTIONS_FOUND: count={len(active_subscriptions)}")
                for sub in active_subscriptions:
                    logger.debug(f"🔔 SUBSCRIPTION_ENDPOINT: {sub.endpoint[:50]}...")

                if not active_subscriptions:
                    logger.warning("🔔 NO_ACTIVE_PUSH_SUBSCRIPTIONS: No active push subscriptions found")
                    return

                streamer_id = details.get('streamer_id')
                stream_id = details.get('stream_id')
                stream_title = details.get('title', 'Stream')
                category_name = details.get('category_name', '')

                # Skip if we don't have essential data
                if not streamer_id:
                    logger.warning("No streamer_id in details, skipping push notifications")
                    return

                # Check if we should send push notifications for this event type and streamer
                should_send = await self.should_notify(int(streamer_id), event_type)
                logger.info(f"🔔 PUSH_NOTIFICATION_CHECK: streamer_id={streamer_id}, event={event_type}, should_send={should_send}")

                if not should_send:
                    logger.warning(f"🔔 PUSH_NOTIFICATIONS_DISABLED: streamer_id={streamer_id}, event={event_type}")
                    return

                # Send appropriate notification based on event type
                successful_sends = 0
                failed_sends = 0

                for subscription in active_subscriptions:
                    try:
                        subscription_data = json.loads(subscription.subscription_data)
                        logger.debug(f"🔔 SENDING_PUSH_TO_SUBSCRIPTION: endpoint={subscription_data.get('endpoint', 'unknown')[:50]}...")

                        success = False
                        if event_type == 'online':
                            success = await self.push_service.send_stream_online_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id) if stream_id else None,
                                category_name
                            )
                        elif event_type == 'offline':
                            success = await self.push_service.send_stream_offline_notification(
                                subscription_data,
                                streamer_name,
                                int(streamer_id)
                            )
                        elif event_type == 'update':
                            success = await self.push_service.send_stream_update_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                category_name,
                                int(streamer_id)
                            )
                        elif event_type == 'favorite_category':
                            success = await self.push_service.send_favorite_category_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                category_name,
                                int(streamer_id)
                            )
                        elif event_type == 'recording_started':
                            success = await self.push_service.send_recording_started_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id) if stream_id else None
                            )
                        elif event_type == 'recording_finished' and stream_id:
                            duration = details.get('duration', 'Unknown')
                            success = await self.push_service.send_recording_finished_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id),
                                duration
                            )

                        if success:
                            successful_sends += 1
                            logger.debug(f"🔔 PUSH_SUCCESS: endpoint={subscription_data.get('endpoint', 'unknown')[:50]}...")
                        else:
                            failed_sends += 1
                            logger.warning(f"🔔 PUSH_FAILED: endpoint={subscription_data.get('endpoint', 'unknown')[:50]}...")

                    except Exception as sub_error:
                        failed_sends += 1
                        logger.error(f"🔔 PUSH_EXCEPTION: {subscription.endpoint[:50]}: {sub_error}")

                        # If subscription is invalid, deactivate it
                        if "410" in str(sub_error) or "expired" in str(sub_error).lower():
                            subscription.is_active = False
                            db.commit()
                            logger.info(f"Deactivated expired push subscription: {subscription.endpoint[:50]}")

                logger.info(f"🔔 PUSH_NOTIFICATION_SUMMARY: event={event_type}, successful={successful_sends}, failed={failed_sends}, total={len(active_subscriptions)}")

        except Exception as e:
            logger.error(f"🔔 PUSH_NOTIFICATION_ERROR: {e}", exc_info=True)
