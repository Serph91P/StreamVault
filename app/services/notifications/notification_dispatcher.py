"""
NotificationDispatcher - Main notification coordination service

Extracted from notification_service.py God Class
Central dispatcher that coordinates WebSocket, external, and push notifications.
"""

import logging
from typing import Dict, Any, Optional
from app.services.communication.websocket_manager import ConnectionManager
from .external_notification_service import ExternalNotificationService
from .push_notification_service import PushNotificationService

logger = logging.getLogger("streamvault")


class NotificationDispatcher:
    """Main notification coordination service"""

    def __init__(self, websocket_manager: Optional[ConnectionManager] = None):
        self.websocket_manager = websocket_manager
        self.external_service = ExternalNotificationService()
        self.push_service = PushNotificationService()

    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict):
        """Main entry point for sending all types of stream notifications"""
        try:
            logger.info(f"🔔 SEND_STREAM_NOTIFICATION: streamer={streamer_name}, event={event_type}, details_keys={list(details.keys())}")

            # Check if we should send notifications for this event type and streamer
            if 'streamer_id' in details:
                should_send = await self.push_service.should_notify(details['streamer_id'], event_type)
                logger.debug(f"Notification check for streamer {details['streamer_id']} and event {event_type}: should_send={should_send}")
                if not should_send:
                    logger.debug(f"Notifications disabled for streamer {details['streamer_id']} and event {event_type}")
                    return

            # Send WebSocket notification first
            await self._send_websocket_notification(streamer_name, event_type, details)

            # Send push notifications to all active subscribers
            await self.push_service.send_push_notifications(streamer_name, event_type, details)

            # Send external notification (Apprise)
            await self.external_service.send_stream_notification(streamer_name, event_type, details)

        except Exception as e:
            logger.error(f"Error in send_stream_notification: {e}", exc_info=True)

    async def _send_websocket_notification(self, streamer_name: str, event_type: str, details: dict):
        """Send WebSocket notification to connected clients"""
        if not self.websocket_manager:
            logger.debug("No WebSocket manager available")
            return

        try:
            # Map event types to correct WebSocket types
            websocket_type = f"stream.{event_type}"
            if event_type == "update":
                websocket_type = "channel.update"

            websocket_notification = {
                "type": websocket_type,
                "data": {
                    "streamer_name": streamer_name,
                    "username": streamer_name,  # For compatibility
                    "title": details.get("title"),
                    "category_name": details.get("category_name"),
                    "language": details.get("language"),
                    "started_at": details.get("started_at"),
                    "url": details.get("url"),
                    "profile_image_url": details.get("profile_image_url"),
                    "streamer_id": details.get("streamer_id"),
                    "twitch_id": details.get("twitch_id"),
                    "is_live": details.get("is_live")
                }
            }
            logger.debug(f"Sending WebSocket notification: {websocket_notification}")
            await self.websocket_manager.send_notification(websocket_notification)

        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {e}")

    async def send_notification(self, message: str, title: str = "StreamVault Notification") -> bool:
        """Send a basic notification via external service"""
        return await self.external_service.send_notification(message, title)

    async def send_test_notification(self) -> bool:
        """Send a test notification"""
        return await self.external_service.send_test_notification()

    async def notify(self, message: Dict[str, Any]):
        """WebSocket notification for compatibility"""
        try:
            if self.websocket_manager:
                await self.websocket_manager.send_notification(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            raise
