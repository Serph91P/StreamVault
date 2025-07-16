"""
NotificationFormatter - Message formatting utilities

Extracted from notification_service.py God Class
Handles formatting of notification messages and titles for different event types.
"""

import logging
from typing import Dict, Tuple

logger = logging.getLogger("streamvault")


class NotificationFormatter:
    """Formats notification messages and titles for different event types"""
    
    @staticmethod
    def format_notification_message(streamer_name: str, event_type: str, details: dict) -> Tuple[str, str]:
        """Format notification message and title based on event type"""
        title = "StreamVault Notification"
    
        if event_type == "online":
            title = f"🟢 {streamer_name} is now live!"
            message = (
                f"Started streaming: {details.get('title', 'No title')}\n"
                f"Category: {details.get('category_name', 'No category')}"
            )
        elif event_type == "offline":
            title = f"🔴 {streamer_name} went offline"
            message = "Stream ended"
        elif event_type == "update":
            title = f"📝 {streamer_name} updated stream"
            message = (
                f"New title: {details.get('title', 'No title')}\n"
                f"Category: {details.get('category_name', 'No category')}"
            )
        elif event_type == "favorite_category":
            title = f"🎮 {streamer_name} spielt ein Favoriten-Spiel!"
            message = (
                f"🎮 {streamer_name} spielt jetzt {details.get('category_name', 'Unknown Game')}!\n\n"
                f"Titel: {details.get('title', 'No title')}\n"
                f"Dieses Spiel ist in deinen Favoriten."
            )
        else:
            title = f"StreamVault: {streamer_name}"
            message = f"Event notification for {streamer_name}"
    
        return title, message

    @staticmethod
    def get_event_title_map() -> Dict[str, str]:
        """Get mapping of event types to default titles"""
        return {
            "online": "is live!",
            "offline": "went offline", 
            "update": "updated stream info",
            "test": "StreamVault Test Notification"
        }
