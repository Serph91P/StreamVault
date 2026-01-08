"""
ExternalNotificationService - Apprise-based external notifications

Extracted from notification_service.py God Class
Handles external notifications via Apprise (Ntfy, Discord, Telegram, etc.)
"""

import logging
from apprise import Apprise, NotifyFormat
from app.models import GlobalSettings, Streamer
from app.database import SessionLocal
from .notification_formatter import NotificationFormatter

logger = logging.getLogger("streamvault")


class ExternalNotificationService:
    """Handles external notifications via Apprise"""

    def __init__(self):
        self.apprise = Apprise()
        self._notification_url = None
        self.formatter = NotificationFormatter()
        self._initialize_apprise()

    def _initialize_apprise(self):
        """Initialize Apprise with the notification URL from settings"""
        try:
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Notifications disabled")
                    return

                if not settings.notification_url:
                    logger.debug("No notification URL configured")
                    return

                url = settings.notification_url.strip()
                self._notification_url = url
                self.apprise = Apprise()

                # Try to add the URL to Apprise
                if self.apprise.add(url):
                    logger.info(f"Apprise initialized successfully with URL: {url}")
                else:
                    logger.error(f"Failed to initialize Apprise with URL: {url}")
                    self._notification_url = None

        except Exception as e:
            logger.error(f"Error initializing Apprise: {e}")
            self._notification_url = None

    async def send_notification(self, message: str, title: str = "StreamVault Notification") -> bool:
        """Send a basic notification"""
        with SessionLocal() as db:
            settings = db.query(GlobalSettings).first()
            if not settings or not settings.notifications_enabled:
                logger.debug("Notifications are disabled, skipping")
                return False
            if not settings.notification_url:
                logger.debug("No notification URLs configured, skipping")
                return False

        # Refresh URLs before sending
        self._initialize_apprise()

        logger.debug(f"Preparing to send notification: {message[:50]}...")
        try:
            result = await self.apprise.async_notify(body=message, title=title)
            if result:
                logger.info("Notification sent successfully")
            else:
                logger.error("Failed to send notification - Apprise returned False")
            return result
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return False

    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict) -> bool:
        """Send external notification via Apprise for stream events"""
        try:
            logger.debug(f"Starting send_stream_notification for {streamer_name}, event type: {event_type}")

            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Global notifications disabled")
                    return False

                # Case insensitive search for streamer
                streamer = db.query(Streamer).filter(Streamer.username.ilike(streamer_name)).first()

                if not streamer:
                    logger.debug(f"Streamer {streamer_name} not found in database")
                    return False

                # Get service-specific URL configuration
                twitch_url = f"https://twitch.tv/{streamer_name}"

                # CRITICAL: Always use original Twitch HTTP URL for notifications
                # External services (Ntfy, Discord, etc.) cannot access local file paths
                profile_image_url = ""

                # Priority 1: Use original Twitch URL (always HTTP, always works)
                if streamer.original_profile_image_url and streamer.original_profile_image_url.startswith("http"):
                    profile_image_url = streamer.original_profile_image_url
                    logger.debug(f"Using original Twitch profile URL: {profile_image_url}")

                # Priority 2: If details has HTTP URL (from EventSub notification)
                elif details.get("profile_image_url") and details["profile_image_url"].startswith("http"):
                    profile_image_url = details["profile_image_url"]
                    logger.debug(f"Using profile URL from EventSub details: {profile_image_url}")

                # Priority 3: Current streamer profile URL (if HTTP)
                elif streamer.profile_image_url and streamer.profile_image_url.startswith("http"):
                    profile_image_url = streamer.profile_image_url
                    logger.debug(f"Using current profile URL: {profile_image_url}")

                # If no suitable URL found, leave empty (notification will use service default icon)
                if not profile_image_url:
                    logger.warning(
                        f"No HTTP profile image URL found for {streamer_name}, notification will use default icon"
                    )

                notification_url = self._get_service_specific_url(
                    base_url=settings.notification_url,
                    twitch_url=twitch_url,
                    profile_image=profile_image_url,  # FIXED: Now always HTTP URL
                    streamer_name=streamer_name,
                    event_type=event_type,
                )

                # Create new Apprise instance
                apprise = Apprise()
                if not apprise.add(notification_url):
                    logger.error(f"Failed to initialize notification URL: {notification_url}")
                    return False

                # Format message using formatter
                title, message = self.formatter.format_notification_message(
                    streamer_name=streamer_name, event_type=event_type, details=details
                )

                # Send notification
                logger.debug(f"Sending notification with title: {title}, message: {message[:50]}...")
                result = await apprise.async_notify(title=title, body=message, body_format=NotifyFormat.TEXT)

                if not result:
                    logger.error("Apprise notification failed to send")

                logger.debug(f"Notification result: {result}")
                return result

        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
            return False

    async def send_test_notification(self) -> bool:
        """Send a test notification using current settings"""
        try:
            if not self._notification_url:
                logger.error("No notification URL configured")
                return False

            # Create new Apprise instance for test
            apprise = Apprise()
            if not apprise.add(self._notification_url):
                logger.error(f"Invalid notification URL: {self._notification_url}")
                return False

            logger.debug(f"Sending test notification via: {self._notification_url}")

            result = await apprise.async_notify(
                title="🔔 StreamVault Test Notification",
                body=(
                    "This is a test notification from StreamVault.\n\n"
                    "If you receive this, your notification settings are working correctly!"
                ),
            )

            if result:
                logger.info("Test notification sent successfully")
                return True

            logger.error("Failed to send test notification")
            return False

        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False

    def _get_service_specific_url(
        self, base_url: str, twitch_url: str, profile_image: str, streamer_name: str, event_type: str
    ) -> str:
        """
        Configure service-specific parameters based on the notification service.

        IMPORTANT: profile_image must be an HTTP URL accessible by external services.
        Local file paths (/recordings/.media/...) will NOT work.
        """

        logger.debug(f"Configuring service-specific URL for {base_url}")

        # Get appropriate title based on event type
        title_map = self.formatter.get_event_title_map()
        title = f"{streamer_name} {title_map.get(event_type, 'notification')}"

        if "ntfy" in base_url:
            # Ntfy configuration
            params = [f"click={twitch_url}", f"priority={'high' if event_type == 'online' else 'default'}"]

            # Event-spezifische Tags
            if event_type == "online":
                params.append("tags=live_stream,online")
            elif event_type == "offline":
                params.append("tags=stream,offline")
            elif event_type == "update":
                params.append("tags=stream,update")
            else:
                params.append("tags=notification")

            # CRITICAL FIX: Use 'attach' for profile images (not 'icon')
            # ntfy 'icon' parameter is for small status icons
            # ntfy 'attach' parameter displays full images like profile pictures
            if profile_image and profile_image.startswith("http"):
                params.append(f"attach={profile_image}")  # FIXED: Changed from icon= to attach=
                logger.debug(f"Added profile image to notification (attach): {profile_image}")
            else:
                logger.debug("No valid HTTP profile image, notification will use default icon")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated ntfy URL: {final_url}")
            return final_url

        elif "discord" in base_url:
            # Discord configuration
            final_url = (
                f"{base_url}?"
                f"avatar_url={profile_image if event_type != 'test' else '/app/frontend/public/ms-icon-310x310.png'}&"
                f"title={title}&"
                f"href={twitch_url}&"
                f"format=markdown"
            )
            logger.debug(f"Generated discord URL: {final_url}")
            return final_url

        elif "telegram" in base_url or "tgram" in base_url:
            # Telegram configuration
            params = []
            if profile_image:
                params.append("image=yes")
            params.append("format=markdown")
            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug(f"Generated telegram URL: {final_url}")
            return final_url

        elif "matrix" in base_url:
            # Matrix configuration
            params = ["msgtype=text", "format=markdown", f"thumbnail={'true' if profile_image else 'false'}"]
            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated matrix URL: {final_url}")
            return final_url

        elif "slack" in base_url:
            # Slack configuration
            final_url = f"{base_url}?" f"footer=yes&" f"image={'yes' if profile_image else 'no'}"
            logger.debug(f"Generated slack URL: {final_url}")
            return final_url

        elif "pover" in base_url:
            # Pushover configuration
            priority = "high" if event_type == "online" else "normal"
            final_url = f"{base_url}?" f"priority={priority}&" f"url={twitch_url}&" f"url_title=Watch Stream"
            logger.debug(f"Generated pushover URL: {final_url}")
            return final_url

        # Default case - return original URL if service not specifically handled
        logger.debug(f"No specific configuration for this service, using base URL: {base_url}")
        return base_url

    async def send_recording_notification(self, streamer_name: str, event_type: str, details: dict = None) -> bool:
        """
        Send notification for recording events (started/failed/completed)

        Args:
            streamer_name: Name of the streamer
            event_type: 'recording_started', 'recording_failed', 'recording_completed'
            details: Additional info (error_message, duration, file_size, quality, etc.)

        Returns:
            True if notification sent successfully
        """
        try:
            # Check if this specific event type is enabled
            from app.database import SessionLocal
            from app.models import GlobalSettings, Streamer

            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings:
                    logger.debug("No global settings found")
                    return False

                # Check if notifications are globally enabled
                if not settings.notifications_enabled:
                    logger.debug("Notifications globally disabled")
                    return False

                if not settings.notification_url:
                    logger.debug("No notification URL configured")
                    return False

                # Check event-specific toggle
                if event_type == "recording_started" and not settings.notify_recording_started:
                    logger.debug("Recording started notifications disabled")
                    return False
                elif event_type == "recording_failed" and not settings.notify_recording_failed:
                    logger.debug("Recording failed notifications disabled")
                    return False
                elif event_type == "recording_completed" and not settings.notify_recording_completed:
                    logger.debug("Recording completed notifications disabled")
                    return False

                # Get streamer for profile image
                streamer = db.query(Streamer).filter(Streamer.username == streamer_name).first()
                if not streamer:
                    logger.debug(f"Streamer {streamer_name} not found")
                    return False

                # Get profile image URL (HTTP only)
                profile_image_url = ""
                if streamer.original_profile_image_url and streamer.original_profile_image_url.startswith("http"):
                    profile_image_url = streamer.original_profile_image_url
                elif details and details.get("profile_image_url", "").startswith("http"):
                    profile_image_url = details["profile_image_url"]

                twitch_url = f"https://twitch.tv/{streamer_name}"

                # Get service-specific URL
                notification_url = self._get_service_specific_url(
                    base_url=settings.notification_url,
                    twitch_url=twitch_url,
                    profile_image=profile_image_url,
                    streamer_name=streamer_name,
                    event_type=event_type,
                )

                # Create Apprise instance
                from apprise import Apprise, NotifyFormat

                apprise = Apprise()
                if not apprise.add(notification_url):
                    logger.error(f"Failed to add notification URL: {notification_url}")
                    return False

                # Format message
                title, message = self.formatter.format_recording_notification(
                    streamer_name=streamer_name, event_type=event_type, details=details or {}
                )

                # Send notification
                logger.debug(f"Sending recording notification: {event_type} for {streamer_name}")
                result = await apprise.async_notify(title=title, body=message, body_format=NotifyFormat.TEXT)

                if result:
                    logger.info(f"✅ Recording notification sent: {event_type} - {streamer_name}")
                else:
                    logger.error(f"❌ Failed to send recording notification: {event_type}")

                return result

        except Exception as e:
            logger.error(f"Error sending recording notification: {e}", exc_info=True)
            return False
