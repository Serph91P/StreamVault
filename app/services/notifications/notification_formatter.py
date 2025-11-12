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
            "test": "StreamVault Test Notification",
            # Recording events (NEW)
            "recording_started": "recording started",
            "recording_failed": "recording failed",
            "recording_completed": "recording completed"
        }
    
    @staticmethod
    def format_recording_notification(streamer_name: str, event_type: str, 
                                     details: dict) -> Tuple[str, str]:
        """Format recording event notifications
        
        Args:
            streamer_name: Name of the streamer
            event_type: 'recording_started', 'recording_failed', 'recording_completed'
            details: Additional info (error_message, duration, file_size, quality, etc.)
        
        Returns:
            Tuple of (title, message) for the notification
        """
        
        if event_type == "recording_started":
            title = f"🔴 Recording Started: {streamer_name}"
            quality = details.get('quality', 'best')
            stream_title = details.get('stream_title', 'N/A')
            category = details.get('category', 'N/A')
            
            message = (
                f"Started recording {streamer_name}'s stream.\n\n"
                f"Quality: {quality}\n"
                f"Title: {stream_title}\n"
                f"Category: {category}"
            )
        
        elif event_type == "recording_failed":
            title = f"❌ Recording Failed: {streamer_name}"
            error = details.get('error_message', 'Unknown error')
            timestamp = details.get('timestamp', 'N/A')
            stream_title = details.get('stream_title', 'N/A')
            category = details.get('category', 'N/A')
            
            message = (
                f"Recording failed for {streamer_name}.\n\n"
                f"❌ Error: {error}\n"
                f"⏰ Time: {timestamp}\n"
                f"📺 Title: {stream_title}\n"
                f"🎮 Category: {category}\n\n"
                f"Check logs for more details."
            )
        
        elif event_type == "recording_completed":
            title = f"✅ Recording Completed: {streamer_name}"
            duration = details.get('duration_minutes', 0)
            file_size_mb = details.get('file_size_mb', 0)
            quality = details.get('quality', 'best')
            
            # Format duration nicely
            hours = duration // 60
            minutes = duration % 60
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            message = (
                f"Recording completed for {streamer_name}.\n\n"
                f"⏱️ Duration: {duration_str}\n"
                f"💾 File size: {file_size_mb} MB\n"
                f"🎬 Quality: {quality}"
            )
        
        else:
            title = f"📹 Recording Event: {streamer_name}"
            message = f"Event: {event_type}"
        
        return title, message

