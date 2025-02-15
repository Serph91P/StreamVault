import logging
import apprise
from typing import List, Optional
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class NotificationService:
    def __init__(self):
        self.settings = settings
        self.apprise = apprise.Apprise()
        self._initialize_apprise()

    def _initialize_apprise(self):
        """Initialize Apprise with configured notification URLs"""
        urls = self.settings.APPRISE_URLS
        logger.debug(f"Initializing Apprise with {len(urls)} configured services")
        
        for url in urls:
            self.apprise.add(url)
            logger.debug(f"Added Apprise URL: {url[:10]}...")  # Log truncated URL for security

    async def send_notification(self, 
                              message: str, 
                              title: str = "StreamVault Notification",
                              urls: Optional[List[str]] = None) -> bool:
        """
        Send notification through configured services
        
        Args:
            message: The notification message
            title: Optional notification title
            urls: Optional list of additional URLs for this notification only
        
        Returns:
            bool: Success status of the notification
        """
        logger.debug(f"Preparing to send notification: {message[:50]}...")

        if urls:
            # Create temporary Apprise instance with additional URLs
            temp_apprise = apprise.Apprise()
            for url in urls:
                temp_apprise.add(url)
            notifier = temp_apprise
        else:
            notifier = self.apprise

        try:
            result = await notifier.async_notify(
                body=message,
                title=title
            )
            
            if result:
                logger.info("Notification sent successfully")
            else:
                logger.warning("Notification failed to send")
                
            return result

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return False

    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict):
        """
        Send formatted stream-related notification
        
        Args:
            streamer_name: Name of the streamer
            event_type: Type of event (online, offline, update)
            details: Additional event details
        """
        templates = {
            "online": f"🟢 {streamer_name} is now live!",
            "offline": f"🔴 {streamer_name} has gone offline",
            "update": f"📝 {streamer_name} updated stream information"
        }

        base_message = templates.get(event_type, f"Event for {streamer_name}")
        
        # Add details to message
        if details.get("title"):
            base_message += f"\nTitle: {details['title']}"
        if details.get("category_name"):
            base_message += f"\nCategory: {details['category_name']}"

        await self.send_notification(base_message)
