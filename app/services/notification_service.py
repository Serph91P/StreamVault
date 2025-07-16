"""
NotificationService - Backward compatibility wrapper

This is a lightweight wrapper around the refactored notification services
to maintain backward compatibility while the codebase migrates to the new structure.

Original God Class (527 lines) split into:
- NotificationDispatcher: Main coordination
- ExternalNotificationService: Apprise-based notifications  
- PushNotificationService: Browser push notifications
- NotificationFormatter: Message formatting
"""

import logging
from typing import Dict, Optional, Any
from app.services.communication.websocket_manager import ConnectionManager
from app.services.notifications import NotificationDispatcher

logger = logging.getLogger("streamvault")


class NotificationService:
    """Backward compatibility wrapper for the refactored notification services"""
    
    def __init__(self, websocket_manager: Optional[ConnectionManager] = None):
        self.dispatcher = NotificationDispatcher(websocket_manager)
        # Legacy properties for compatibility
        self.websocket_manager = websocket_manager
        self.apprise = self.dispatcher.external_service.apprise
        self._notification_url = self.dispatcher.external_service._notification_url
        self.push_service = self.dispatcher.push_service.push_service

    async def send_notification(self, message: str, title: str = "StreamVault Notification") -> bool:
        """Send a basic notification"""
        return await self.dispatcher.send_notification(message, title)

    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict):
        """Send stream notification - main entry point"""
        await self.dispatcher.send_stream_notification(streamer_name, event_type, details)

    async def send_test_notification(self) -> bool:
        """Send a test notification"""
        return await self.dispatcher.send_test_notification()

    async def notify(self, message: Dict[str, Any]):
        """WebSocket notification for compatibility"""
        await self.dispatcher.notify(message)

    async def should_notify(self, streamer_id: int, event_type: str) -> bool:
        """Check if notifications should be sent"""
        return await self.dispatcher.push_service.should_notify(streamer_id, event_type)

    def _format_notification_message(self, streamer_name: str, event_type: str, details: dict) -> tuple[str, str]:
        """Format notification message - legacy method"""
        return self.dispatcher.external_service.formatter.format_notification_message(
            streamer_name, event_type, details
        )

    def _get_service_specific_url(self, base_url: str, twitch_url: str, profile_image: str, 
                                 streamer_name: str, event_type: str, 
                                 original_image_url: Optional[str] = None) -> str:
        """Get service-specific URL - legacy method"""
        return self.dispatcher.external_service._get_service_specific_url(
            base_url, twitch_url, profile_image, streamer_name, event_type, original_image_url
        )

    async def _send_push_notifications(self, streamer_name: str, event_type: str, details: dict):
        """Send push notifications - legacy method"""
        await self.dispatcher.push_service.send_push_notifications(streamer_name, event_type, details)

    async def _send_external_notification(self, streamer_name: str, event_type: str, details: dict):
        """Send external notification - legacy method"""
        await self.dispatcher.external_service.send_stream_notification(streamer_name, event_type, details)

    def _initialize_apprise(self):
        """Initialize Apprise - legacy method"""
        self.dispatcher.external_service._initialize_apprise()


# Legacy function for backward compatibility
async def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user info from Twitch API including profile image"""
    try:
        from app.services.api.twitch_api import twitch_api
        users = await twitch_api.get_users_by_id([user_id])
        return users[0] if users else None
    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
        return None
