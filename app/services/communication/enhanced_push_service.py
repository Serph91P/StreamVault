"""
Enhanced Push Service using a more modern implementation
DEPRECATED: Use ModernWebPushService directly instead
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from app.config.settings import settings
from .webpush_service import ModernWebPushService, WebPushException

logger = logging.getLogger("streamvault")

# DEPRECATED: Use ModernWebPushService directly


class EnhancedPushService:
    def __init__(self):
        self.settings = settings
        # Lazy initialization - web_push_service will be created on first use
        self._web_push_service: Optional[ModernWebPushService] = None
        self._initialization_attempted = False

    @property
    def web_push_service(self) -> Optional[ModernWebPushService]:
        """Lazy initialization of web push service - loads VAPID keys on first use"""
        if self._web_push_service is not None:
            return self._web_push_service

        if self._initialization_attempted:
            return None  # Already tried and failed

        self._initialization_attempted = True

        # Get VAPID keys from settings (may trigger database load)
        vapid_keys = self.settings.get_vapid_keys()
        vapid_private_key = vapid_keys.get("private_key")
        vapid_public_key = vapid_keys.get("public_key")

        if not vapid_private_key or not vapid_public_key:
            logger.warning(
                "VAPID keys not available, web push service will be disabled"
            )
            return None

        # VAPID claims for the sender
        vapid_claims = {
            "sub": vapid_keys.get("claims_sub", "mailto:admin@streamvault.local")
        }

        try:
            self._web_push_service = ModernWebPushService(
                vapid_private_key=vapid_private_key, vapid_claims=vapid_claims
            )
            logger.info("Enhanced Web Push Service initialized successfully (lazy)")
            return self._web_push_service
        except Exception:
            logger.warning("Failed to initialize Web Push Service")
            return None

    @property
    def vapid_public_key(self) -> Optional[str]:
        """Get VAPID public key from settings"""
        vapid_keys = self.settings.get_vapid_keys()
        return vapid_keys.get("public_key")

    def reset_initialization(self):
        """Reset initialization state to allow retry after VAPID keys become available"""
        self._web_push_service = None
        self._initialization_attempted = False
        logger.info("EnhancedPushService initialization state reset")

    async def send_notification(
        self,
        subscription: Union[Dict[str, Any], str],
        notification_data: Dict[str, Any],
    ) -> bool:
        """Send using the shared transport; let callers persist confirmed expiry."""
        try:
            service = self.web_push_service
            if not service or not self.vapid_public_key:
                return False
            if isinstance(subscription, str):
                subscription = json.loads(subscription)
            return service.send_notification(subscription, notification_data, ttl=43200)
        except WebPushException:
            raise
        except Exception:
            logger.warning("Push notification could not be sent")
            return False

    # Die folgenden Methoden bleiben unverändert, nur kopiere ich die erste als Beispiel:

    async def send_stream_online_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        streamer_id: int,
        stream_id: Optional[int] = None,
        category_name: Optional[str] = None,
    ) -> bool:
        """Send a notification when a stream goes online"""
        # Use same format as Apprise notifications
        title = f"🟢 {streamer_name} is now live!"
        body = f"Started streaming: {stream_title or 'No title'}"
        if category_name:
            body += f"\nCategory: {category_name}"

        notification_data = {
            "title": title,
            "body": body,
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_online",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"https://twitch.tv/{streamer_name.lower()}",
                "internal_url": f"/streamer/{streamer_id}",
            },
            "actions": [
                {"action": "view_stream", "title": "View Stream"},
                {"action": "dismiss", "title": "Dismiss"},
            ],
            "requireInteraction": True,
            "tag": f"stream-online-{streamer_id}",
        }

        return await self.send_notification(subscription, notification_data)

    async def send_recording_started_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        streamer_id: int,
        stream_id: Optional[int] = None,
    ) -> bool:
        """Send a notification when recording starts"""
        # Simple recording notification - no actions needed for recording start
        notification_data = {
            "title": f"📹 Recording started: {streamer_name}",
            "body": f"Now recording: {stream_title or 'Stream'}",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "recording_started",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"/streamer/{streamer_id}",
            },
            "tag": f"recording-started-{streamer_id}",
        }

        return await self.send_notification(subscription, notification_data)

    async def send_recording_finished_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        streamer_id: int,
        stream_id: int,
        duration: str,
    ) -> bool:
        """Send a notification when recording finishes"""
        notification_data = {
            "title": f"✅ Recording finished: {streamer_name}",
            "body": f"Recorded {duration}: {stream_title or 'Stream'}",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "recording_finished",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"/streamer/{streamer_id}/stream/{stream_id}/watch",
            },
            "actions": [
                {"action": "view_recording", "title": "Watch Recording"},
                {"action": "dismiss", "title": "Dismiss"},
            ],
            "tag": f"recording-finished-{stream_id}",
        }

        return await self.send_notification(subscription, notification_data)

    async def send_stream_offline_notification(
        self, subscription: Dict[str, Any], streamer_name: str, streamer_id: int
    ) -> bool:
        """Send a notification when a stream goes offline"""
        # Use same format as Apprise notifications - simple offline notification
        notification_data = {
            "title": f"🔴 {streamer_name} went offline",
            "body": "Stream ended",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_offline",
            "data": {"streamer_id": streamer_id, "url": f"/streamer/{streamer_id}"},
            "tag": f"stream-offline-{streamer_id}",
        }

        return await self.send_notification(subscription, notification_data)

    async def send_stream_update_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        category_name: str,
        streamer_id: int,
    ) -> bool:
        """Send a notification when stream info is updated"""
        # Use same format as Apprise notifications
        title = f"📝 {streamer_name} updated stream"
        body = f"New title: {stream_title or 'No title'}"
        if category_name:
            body += f"\nCategory: {category_name}"

        notification_data = {
            "title": title,
            "body": body,
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_update",
            "data": {
                "streamer_id": streamer_id,
                "url": f"https://twitch.tv/{streamer_name.lower()}",
                "internal_url": f"/streamer/{streamer_id}",
            },
            "actions": [
                {"action": "view_stream", "title": "View Stream"},
                {"action": "dismiss", "title": "Dismiss"},
            ],
            "requireInteraction": True,
            "tag": f"stream-update-{streamer_id}",
        }

        return await self.send_notification(subscription, notification_data)

    async def send_favorite_category_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        category_name: str,
        streamer_id: int,
    ) -> bool:
        """Send a notification when a streamer plays a favorite game"""
        # Use same format as Apprise notifications
        title = f"🎮 {streamer_name} spielt ein Favoriten-Spiel!"
        body = f"🎮 {streamer_name} spielt jetzt {category_name}!\n\nTitel: {stream_title or 'No title'}\nDieses Spiel ist in deinen Favoriten."

        notification_data = {
            "title": title,
            "body": body,
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "favorite_category",
            "data": {
                "streamer_id": streamer_id,
                "category_name": category_name,
                "url": f"https://twitch.tv/{streamer_name.lower()}",
                "internal_url": f"/streamer/{streamer_id}",
            },
            "actions": [
                {"action": "view_stream", "title": "View Stream"},
                {"action": "dismiss", "title": "Dismiss"},
            ],
            "requireInteraction": True,
            "tag": f"favorite-category-{streamer_id}",
        }

        return await self.send_notification(subscription, notification_data)


# Shared instance for dependency injection
enhanced_push_service = EnhancedPushService()
