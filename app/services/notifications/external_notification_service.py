"""
ExternalNotificationService - Apprise-based external notifications

Extracted from notification_service.py God Class
Handles external notifications via Apprise (Ntfy, Discord, Telegram, etc.)
"""

import logging
import re
from typing import Optional
from apprise import Apprise, NotifyFormat
from app.models import GlobalSettings, Streamer
from app.database import SessionLocal
from .notification_formatter import NotificationFormatter

logger = logging.getLogger("streamvault")


def optimize_profile_image_for_notification(url: str, target_size: int = 70) -> str:
    """
    Optimize Twitch profile image URL for notification avatars.

    Twitch CDN supports these sizes: 70x70, 150x150, 300x300
    Apprise typically uses 32x32, 72x72, 128x128, 256x256 icons.

    For notification avatars, 70x70 is ideal (close to Apprise's 72x72 standard)
    and reduces bandwidth/loading time.

    Args:
        url: Original Twitch profile image URL (usually 300x300)
        target_size: Desired size (default 70 for notifications)

    Returns:
        Optimized URL with smaller image size
    """
    if not url or not url.startswith("http"):
        return url

    # Match Twitch CDN profile image pattern: -profile_image-{size}x{size}.png/jpg
    # Example: https://static-cdn.jtvnw.net/jtv_user_pictures/xxx-profile_image-300x300.png
    pattern = r"(-profile_image-)\d+x\d+(\.(?:png|jpg|jpeg|webp))"
    replacement = rf"\g<1>{target_size}x{target_size}\2"

    optimized_url = re.sub(pattern, replacement, url, flags=re.IGNORECASE)

    if optimized_url != url:
        logger.debug(f"Optimized profile image: {url} -> {optimized_url}")

    return optimized_url


def get_local_cached_profile_url(streamer: "Streamer") -> Optional[str]:
    """
    Get the public URL for a locally cached profile image.

    This allows external notification services to fetch the profile image
    from our server instead of relying on Twitch CDN.

    Benefits:
    - Works even if Twitch CDN is unreachable
    - Faster local access
    - Consistent image availability

    Args:
        streamer: Streamer model with profile_image_url

    Returns:
        Public HTTP URL for the cached image, or None if not cached locally
    """
    try:
        from app.config.settings import settings

        # Check if the streamer has a locally cached profile image
        if not streamer.profile_image_url:
            return None

        # Cached images have path format: /recordings/.media/profiles/profile_avatar_{twitch_id}.jpg
        if not streamer.profile_image_url.startswith("/recordings/.media/profiles/"):
            return None

        # Extract filename from the local path
        # e.g., "/recordings/.media/profiles/profile_avatar_12345.jpg" -> "profile_avatar_12345.jpg"
        filename = streamer.profile_image_url.split("/")[-1]

        if not filename or not filename.startswith("profile_avatar_"):
            return None

        # Construct the public URL using BASE_URL
        # The /data/images/profiles/{filename} endpoint serves these files without auth
        base_url = settings.BASE_URL.rstrip("/")
        public_url = f"{base_url}/data/images/profiles/{filename}"

        logger.debug(f"Using locally cached profile image: {public_url}")
        return public_url

    except Exception as e:
        logger.debug(f"Could not get local cached profile URL: {e}")
        return None


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

                # Profile image URL priority:
                # 1. Locally cached image via BASE_URL (reliable, fast, always available)
                # 2. Original Twitch HTTP URL (fallback, requires Twitch CDN to be reachable)
                # 3. EventSub details URL (from notification payload)
                profile_image_url = ""

                # Priority 1: Use locally cached profile image if available
                # This serves the image from our server via /data/images/profiles/{filename}
                local_cached_url = get_local_cached_profile_url(streamer)
                if local_cached_url:
                    profile_image_url = local_cached_url
                    logger.debug(f"Using locally cached profile image: {profile_image_url}")

                # Priority 2: Use original Twitch URL (always HTTP, always works)
                elif streamer.original_profile_image_url and streamer.original_profile_image_url.startswith("http"):
                    profile_image_url = streamer.original_profile_image_url
                    logger.debug(f"Using original Twitch profile URL: {profile_image_url}")
                    # Optimize image size for Twitch CDN URLs
                    profile_image_url = optimize_profile_image_for_notification(profile_image_url)

                # Priority 3: If details has HTTP URL (from EventSub notification)
                elif details.get("profile_image_url") and details["profile_image_url"].startswith("http"):
                    profile_image_url = details["profile_image_url"]
                    logger.debug(f"Using profile URL from EventSub details: {profile_image_url}")
                    # Optimize image size for Twitch CDN URLs
                    profile_image_url = optimize_profile_image_for_notification(profile_image_url)

                # Priority 4: Current streamer profile URL (if HTTP)
                elif streamer.profile_image_url and streamer.profile_image_url.startswith("http"):
                    profile_image_url = streamer.profile_image_url
                    logger.debug(f"Using current profile URL: {profile_image_url}")
                    # Optimize image size for Twitch CDN URLs
                    profile_image_url = optimize_profile_image_for_notification(profile_image_url)

                # If no suitable URL found, leave empty (notification will use service default icon)
                if not profile_image_url:
                    logger.warning(
                        f"No profile image URL found for {streamer_name}, notification will use default icon"
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
            # Ntfy configuration via Apprise
            # See: https://github.com/caronc/apprise/wiki/Notify_ntfy
            #
            # Key parameters:
            # - avatar_url: Overrides the Apprise icon with streamer profile pic
            # - image: Defaults to 'yes' which attaches an image. Set to 'no' to disable
            # - icon: Native ntfy icon URL (separate from Apprise image handling)

            params = [f"click={twitch_url}", f"priority={'high' if event_type == 'online' else 'default'}"]

            # Event-specific tags (text only to avoid duplicate emoji)
            if event_type == "online":
                params.append("tags=live")
            elif event_type == "offline":
                params.append("tags=offline")
            elif event_type == "update":
                params.append("tags=update")
            elif event_type == "recording_started":
                params.append("tags=recording")
            elif event_type == "recording_completed":
                params.append("tags=recording_complete")
            elif event_type == "recording_failed":
                params.append("tags=recording_failed")
            else:
                params.append("tags=notification")

            # Use avatar_url to override the Apprise notification icon with streamer profile
            # Also set image=no to prevent duplicate image attachment
            if profile_image and profile_image.startswith("http"):
                params.append(f"avatar_url={profile_image}")  # Override Apprise icon
                params.append("image=no")  # Disable automatic image attachment (prevents duplicate)
                logger.debug(f"Set ntfy avatar_url to streamer profile: {profile_image}")
            else:
                params.append("image=no")  # Still disable image since we have no profile
                logger.debug("No valid HTTP profile image, notification will use default icon")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated ntfy URL: {final_url}")
            return final_url

        elif "discord" in base_url:
            # Discord configuration
            # avatar_url sets the webhook avatar (streamer profile pic)
            # image=yes enables image embedding in the message
            params = [
                f"title={title}",
                f"href={twitch_url}",
                "format=markdown"
            ]

            # Only add avatar_url if we have a valid HTTP profile image
            if profile_image and profile_image.startswith("http"):
                params.append(f"avatar_url={profile_image}")
                params.append("image=yes")  # Enable image embedding
                logger.debug(f"Discord notification using profile image: {profile_image}")
            else:
                logger.debug("Discord notification will use default avatar (no HTTP profile image)")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated discord URL: {final_url}")
            return final_url

        elif "telegram" in base_url or "tgram" in base_url:
            # Telegram configuration
            # Use 'image' parameter with the actual URL, not just yes/no
            params = ["format=markdown"]

            if profile_image and profile_image.startswith("http"):
                # Telegram can embed images via the image parameter with URL
                params.append(f"image={profile_image}")
                logger.debug(f"Telegram notification using profile image: {profile_image}")

            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug(f"Generated telegram URL: {final_url}")
            return final_url

        elif "matrix" in base_url:
            # Matrix configuration
            params = ["msgtype=text", "format=markdown"]

            if profile_image and profile_image.startswith("http"):
                params.append("thumbnail=true")
                params.append(f"image={profile_image}")
                logger.debug(f"Matrix notification using profile image: {profile_image}")
            else:
                params.append("thumbnail=false")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated matrix URL: {final_url}")
            return final_url

        elif "slack" in base_url:
            # Slack configuration
            # Slack uses 'image' and 'thumb' parameters for embedding images
            params = ["footer=yes"]

            if profile_image and profile_image.startswith("http"):
                params.append("image=yes")
                params.append(f"thumb={profile_image}")  # Thumbnail in attachment
                logger.debug(f"Slack notification using profile image: {profile_image}")
            else:
                params.append("image=no")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated slack URL: {final_url}")
            return final_url

        elif "pover" in base_url:
            # Pushover configuration
            # Pushover supports image attachment via 'attachment' parameter
            params = [
                f"priority={'high' if event_type == 'online' else 'normal'}",
                f"url={twitch_url}",
                "url_title=Watch Stream"
            ]

            if profile_image and profile_image.startswith("http"):
                params.append(f"attachment={profile_image}")
                logger.debug(f"Pushover notification using profile image: {profile_image}")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated pushover URL: {final_url}")
            return final_url

        elif "gotify" in base_url:
            # Gotify configuration
            # Gotify uses 'image' parameter for embedding images
            params = [f"priority={'8' if event_type == 'online' else '5'}"]

            if profile_image and profile_image.startswith("http"):
                params.append(f"image={profile_image}")
                logger.debug(f"Gotify notification using profile image: {profile_image}")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated gotify URL: {final_url}")
            return final_url

        elif "pbul" in base_url or "pushbullet" in base_url:
            # Pushbullet configuration
            params = ["format=text"]

            if profile_image and profile_image.startswith("http"):
                params.append(f"image={profile_image}")
                logger.debug(f"Pushbullet notification using profile image: {profile_image}")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated pushbullet URL: {final_url}")
            return final_url

        elif "msteams" in base_url or "teams" in base_url:
            # Microsoft Teams configuration
            params = []

            if profile_image and profile_image.startswith("http"):
                params.append(f"image={profile_image}")
                logger.debug(f"Teams notification using profile image: {profile_image}")

            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug(f"Generated teams URL: {final_url}")
            return final_url

        # Default case - try to add avatar_url/image parameter for unknown services
        # Many Apprise services support these common parameters
        if profile_image and profile_image.startswith("http"):
            separator = "&" if "?" in base_url else "?"
            final_url = f"{base_url}{separator}avatar_url={profile_image}&image=yes"
            logger.debug(f"Using default avatar_url/image for unknown service: {final_url}")
            return final_url

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

                # Profile image URL priority:
                # 1. Locally cached image via BASE_URL (reliable, fast, always available)
                # 2. Original Twitch HTTP URL (fallback)
                # 3. EventSub details URL
                profile_image_url = ""

                # Priority 1: Use locally cached profile image if available
                local_cached_url = get_local_cached_profile_url(streamer)
                if local_cached_url:
                    profile_image_url = local_cached_url
                    logger.debug(f"Using locally cached profile image: {profile_image_url}")
                # Priority 2: Original Twitch URL
                elif streamer.original_profile_image_url and streamer.original_profile_image_url.startswith("http"):
                    profile_image_url = streamer.original_profile_image_url
                    profile_image_url = optimize_profile_image_for_notification(profile_image_url)
                # Priority 3: From notification details
                elif details and details.get("profile_image_url", "").startswith("http"):
                    profile_image_url = details["profile_image_url"]
                    profile_image_url = optimize_profile_image_for_notification(profile_image_url)

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
