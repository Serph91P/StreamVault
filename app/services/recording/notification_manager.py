"""
Notification handling for the recording service.

This module is responsible for sending various notifications about recording status.
"""

import logging
import asyncio
from typing import Dict, Any
from cachetools import TTLCache
from app.config.constants import CACHE_CONFIG

# Try to import notification utilities
logger = logging.getLogger("streamvault")

# Check if notification_utils module is available
try:
    from app.utils.notification_utils import send_push_notification

    logger.info("Successfully imported notification_utils")
except ImportError as e:
    logger.warning(f"Could not import notification_utils: {e}")
    # Define a fallback notification function

    async def send_push_notification(title="", body="", data=None, **kwargs):
        logger.info(f"[FALLBACK] Would send notification: {title} - {body}")
        return {"sent": 0, "failed": 0, "skipped": 1, "fallback": True}


from app.models import Stream


class NotificationManager:
    """Manager for sending notifications about recordings"""

    def __init__(self, config_manager=None):
        """Initialize the notification manager

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.notifications_enabled = self._get_notifications_enabled()
        # TTLCache automatically evicts old entries (prevents memory leaks)
        self.notification_debounce = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE, ttl=CACHE_CONFIG.NOTIFICATION_DEBOUNCE_TTL
        )

    def _get_notifications_enabled(self) -> bool:
        """Check if notifications are enabled in config"""
        if self.config_manager:
            return self.config_manager.get_config_value("notifications_enabled", default=True)
        return True  # Default to enabled if no config manager

    async def notify_recording_started(self, stream: Stream, metadata: Dict[str, Any]) -> None:
        """Send notification that recording has started

        Args:
            stream: Stream model object
            metadata: Recording metadata
        """
        if not self.notifications_enabled:
            return

        try:
            # Debounce notifications (don't send more than one every 5 minutes for same stream)
            stream_id = stream.id
            current_time = asyncio.get_event_loop().time()
            last_notif_time = self.notification_debounce.get(f"start_{stream_id}", 0)

            if current_time - last_notif_time < 300:  # 5 minutes in seconds
                logger.debug(f"Skipping start notification for stream {stream_id} (debounced)")
                return

            self.notification_debounce[f"start_{stream_id}"] = current_time

            # Prepare notification data
            streamer_name = stream.streamer.username if stream.streamer else "Unknown"
            title = f"Recording Started: {streamer_name}"
            body = f"Recording started for {streamer_name}"

            if "resolution" in metadata:
                body += f" ({metadata['resolution']})"

            data = {
                "action": "recording_started",
                "stream_id": stream.id,
                "stream_name": streamer_name,
                "category": stream.category_name or "Uncategorized",
            }

            # Send notification
            await send_push_notification(title=title, body=body, data=data)
            logger.info(f"Sent recording start notification for stream {streamer_name}")

        except Exception as e:
            logger.error(f"Error sending start notification: {e}", exc_info=True)

    async def notify_recording_completed(
        self, stream: Stream, duration_seconds: int, file_path: str, success: bool = True
    ) -> None:
        """Send notification that recording has completed

        Args:
            stream: Stream model object
            duration_seconds: Duration of recording in seconds
            file_path: Path to recorded file
            success: Whether recording completed successfully
        """
        if not self.notifications_enabled:
            return

        try:
            # Format duration nicely
            duration_str = self._format_duration(duration_seconds)

            # Prepare notification data
            streamer_name = stream.streamer.username if stream.streamer else "Unknown"
            title = f"Recording {'Completed' if success else 'Failed'}: {streamer_name}"
            body = f"Recording {streamer_name} {'completed' if success else 'failed'}"

            if duration_str and success:
                body += f" ({duration_str})"

            data = {
                "action": "recording_completed",
                "stream_id": stream.id,
                "stream_name": streamer_name,
                "success": success,
                "duration": duration_seconds,
                "file_path": file_path,
            }

            # Send notification
            await send_push_notification(title=title, body=body, data=data)
            logger.info(f"Sent recording completion notification for stream {streamer_name}")

        except Exception as e:
            logger.error(f"Error sending completion notification: {e}", exc_info=True)

    async def notify_recording_error(self, stream: Stream, error_message: str) -> None:
        """Send notification about recording error

        Args:
            stream: Stream model object
            error_message: Error message
        """
        if not self.notifications_enabled:
            return

        try:
            # Prepare notification data
            streamer_name = stream.streamer.username if stream.streamer else "Unknown"
            title = f"Recording Error: {streamer_name}"
            body = f"Error recording {streamer_name}: {error_message[:100]}"  # Truncate long messages

            data = {
                "action": "recording_error",
                "stream_id": stream.id,
                "stream_name": streamer_name,
                "error": error_message,
            }

            # Send notification
            await send_push_notification(title=title, body=body, data=data)
            logger.info(f"Sent recording error notification for stream {streamer_name}")

        except Exception as e:
            logger.error(f"Error sending error notification: {e}", exc_info=True)

    def _format_duration(self, seconds: int) -> str:
        """Format seconds into human-readable duration

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "2h 15m")
        """
        if seconds < 60:
            return f"{seconds}s"

        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m {seconds % 60}s"

        hours = minutes // 60
        minutes = minutes % 60

        if hours < 24:
            return f"{hours}h {minutes}m"

        days = hours // 24
        hours = hours % 24

        return f"{days}d {hours}h {minutes}m"
