"""
Utility functions for sending notifications.

This module provides helper functions for sending different types of notifications.
"""
import logging
import json
import time
from typing import Dict, Any

logger = logging.getLogger("streamvault")

# Use a global variable to store the push service
_enhanced_push_service = None
# We'll use lazy imports to avoid circular dependencies


async def send_push_notification(
    title: str = "",
    body: str = "",
    data: Dict[str, Any] = None,
    icon: str = "/android-icon-192x192.png",
    badge: str = "/android-icon-96x96.png",
    require_interaction: bool = True,
    db=None,
    filter_inactive: bool = True
) -> Dict[str, int]:
    """
    Send a push notification to all active subscriptions.

    Args:
        title: The notification title
        body: The notification body text
        data: Additional data to include with the notification
        icon: URL to an icon for the notification
        badge: URL to a badge for the notification
        require_interaction: Whether the notification requires user interaction
        db: Database session (optional, will be created if not provided)
        filter_inactive: Whether to filter out inactive subscriptions

    Returns:
        Dict containing counts of successful and failed notifications
    """
    try:
        # Import here to avoid circular dependencies
        from app.database import get_db
        from app.models import PushSubscription, GlobalSettings

        # Lazy import the enhanced_push_service
        global _enhanced_push_service
        if _enhanced_push_service is None:
            try:
                # Lazy import to avoid circular dependencies
                from importlib import import_module
                enhanced_push_service = import_module("app.services.enhanced_push_service").enhanced_push_service
                _enhanced_push_service = enhanced_push_service
                logger.debug("Successfully loaded enhanced_push_service")
            except ImportError as e:
                logger.error(f"Failed to import enhanced_push_service: {e}")
                # Define a fallback service

                class FallbackPushService:
                    async def send_notification(self, *args, **kwargs):
                        logger.info(f"[FALLBACK] Would send notification with args: {args}, kwargs: {kwargs}")
                        return True
                _enhanced_push_service = FallbackPushService()

        # Create a database session if none provided
        close_db = False
        if db is None:
            db = next(get_db())
            close_db = True

        # Format the notification data
        if data is None:
            data = {}

        notification_data = {
            "title": title,
            "body": body,
            "icon": icon,
            "badge": badge,
            "requireInteraction": require_interaction,
            "timestamp": int(time.time() * 1000),
            "data": data
        }

        # Check if notifications are globally enabled
        global_settings = db.query(GlobalSettings).first()
        if not global_settings or not global_settings.notifications_enabled:
            logger.debug("Push notifications are disabled globally")
            return {"sent": 0, "failed": 0, "skipped": 0}

        # Get active push subscriptions
        query = db.query(PushSubscription)
        if filter_inactive:
            query = query.filter(PushSubscription.is_active.is_(True))

        subscriptions = query.all()

        if not subscriptions:
            logger.debug("No active push subscriptions found")
            return {"sent": 0, "failed": 0, "skipped": 0}

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        # Send the notification to each subscription
        for subscription in subscriptions:
            try:
                # Parse subscription data
                subscription_data = json.loads(subscription.subscription_data)

                # Skip if no endpoint
                if "endpoint" not in subscription_data:
                    skipped_count += 1
                    continue

                # Send the notification
                success = await _enhanced_push_service.send_notification(
                    subscription_data,
                    notification_data
                )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send push notification: {e}")

        # Close db if we created it
        if close_db:
            db.close()

        return {
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count
        }

    except Exception as e:
        logger.error(f"Error sending push notifications: {e}")
        return {"sent": 0, "failed": 0, "skipped": 1, "error": str(e)}
