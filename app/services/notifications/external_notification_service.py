"""
ExternalNotificationService - Apprise-based external notifications

Extracted from notification_service.py God Class
Handles external notifications via Apprise (Ntfy, Discord, Telegram, etc.)
"""

import logging
import os
import re
from collections.abc import Callable
from typing import Literal, Optional
from urllib.parse import quote
from apprise import Apprise, NotifyFormat
from app.models import GlobalSettings, Streamer, Stream
from sqlalchemy.orm import Session
from app.config.settings import Settings
from app.database import SessionLocal
from .notification_formatter import NotificationFormatter
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


def optimize_profile_image_for_notification(url: str, target_size: int = 150) -> str:
    """
    Optimize Twitch profile image URL for notification avatars.

    Twitch CDN supports these sizes: 70x70, 150x150, 300x300
    Apprise typically uses 32x32, 72x72, 128x128, 256x256 icons.

    For notification avatars, 150x150 provides good quality for most services
    while keeping bandwidth reasonable. 70x70 was too small for some services.

    Args:
        url: Original Twitch profile image URL (usually 300x300)
        target_size: Desired size (default 150 for good quality on mobile)

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


def get_local_cached_profile_url(
    streamer: "Streamer", configuration: Settings | None = None
) -> Optional[str]:
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

        # Cast to str for type safety (SQLAlchemy Column -> str at runtime)
        # Use getattr to safely get the value and check if it's truthy
        profile_url_raw = getattr(streamer, "profile_image_url", None)
        profile_url = str(profile_url_raw) if profile_url_raw else None
        if not profile_url:
            return None

        # Cached images have path format: /recordings/.media/profiles/profile_avatar_{twitch_id}.jpg
        if not profile_url.startswith("/recordings/.media/profiles/"):
            return None

        # Extract filename from the local path
        # e.g., "/recordings/.media/profiles/profile_avatar_12345.jpg" -> "profile_avatar_12345.jpg"
        filename = profile_url.split("/")[-1]

        if not filename or not filename.startswith("profile_avatar_"):
            return None

        # Construct the public URL using BASE_URL
        # The /data/images/profiles/{filename} endpoint serves these files without auth
        base_url = (configuration or settings).BASE_URL.rstrip("/")
        public_url = f"{base_url}/data/images/profiles/{filename}"

        logger.debug(f"Using locally cached profile image: {public_url}")
        return public_url

    except Exception as e:
        logger.debug(f"Could not get local cached profile URL: {e}")
        return None


class ExternalNotificationService:
    """Handles external notifications via Apprise"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        settings: Settings | None = None,
    ):
        self._session_factory = session_factory
        self._settings = settings
        self.apprise = Apprise()
        self._notification_url: str | None = None
        self.formatter = NotificationFormatter()

    def _initialize_apprise(self) -> Apprise | None:
        """Initialize Apprise with the notification URL from settings"""
        self._notification_url = None
        try:
            with (self._session_factory or SessionLocal)() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Notifications disabled")
                    return None

                if not settings.notification_url:
                    logger.debug("No notification URL configured")
                    return None

                url = settings.notification_url.strip()
                self._notification_url = url
                apprise = Apprise()

                # Keep each in-flight operation's transport local to its snapshot.
                if apprise.add(url):
                    self.apprise = apprise
                    logger.info("Apprise initialized successfully")
                    return apprise
                else:
                    logger.error("Failed to initialize Apprise URL")
                    self._notification_url = None

        except Exception as e:
            logger.error("Apprise initialization failed (%s)", type(e).__name__)
            self._notification_url = None
        return None

    async def send_notification(
        self, message: str, title: str = "StreamVault Notification"
    ) -> bool:
        """Send a basic notification"""
        try:
            apprise = await run_in_thread_pool(self._initialize_apprise)
            if apprise is None:
                return False
            result = bool(
                await run_in_thread_pool(apprise.notify, body=message, title=title)
            )
            if result:
                logger.info("Notification sent successfully")
            else:
                logger.error("Failed to send notification - Apprise returned False")
            return result
        except Exception as e:
            logger.error("Notification delivery failed (%s)", type(e).__name__)
            return False

    def _prepare_stream_notification(
        self, streamer_name: str, event_type: str, details: dict[str, object]
    ) -> tuple[Apprise, str, str] | Literal[False]:
        """Send external notification via Apprise for stream events"""
        try:
            logger.debug(
                f"Starting send_stream_notification for {streamer_name}, event type: {event_type}"
            )

            with (self._session_factory or SessionLocal)() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Global notifications disabled")
                    return False
                if not settings.notification_url:
                    return False

                # Case insensitive search for streamer
                streamer = (
                    db.query(Streamer)
                    .filter(Streamer.username.ilike(streamer_name))
                    .first()
                )

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

                # Cast SQLAlchemy columns to str for type safety
                original_url = (
                    str(streamer.original_profile_image_url)
                    if getattr(streamer, "original_profile_image_url", None)
                    else ""
                )
                current_url = (
                    str(streamer.profile_image_url)
                    if getattr(streamer, "profile_image_url", None)
                    else ""
                )

                # Priority 1: Use locally cached profile image if available
                # This serves the image from our server via /data/images/profiles/{filename}
                local_cached_url = get_local_cached_profile_url(
                    streamer, self._settings
                )
                if local_cached_url:
                    profile_image_url = local_cached_url
                    logger.debug(
                        f"Using locally cached profile image: {profile_image_url}"
                    )

                # Priority 2: Use original Twitch URL (always HTTP, always works)
                elif original_url and original_url.startswith("http"):
                    profile_image_url = original_url
                    logger.debug(
                        f"Using original Twitch profile URL: {profile_image_url}"
                    )
                    # Optimize image size for Twitch CDN URLs
                    profile_image_url = optimize_profile_image_for_notification(
                        profile_image_url
                    )

                # Priority 3: If details has HTTP URL (from EventSub notification)
                elif details.get("profile_image_url") and str(
                    details["profile_image_url"]
                ).startswith("http"):
                    profile_image_url = str(details["profile_image_url"])
                    logger.debug(
                        f"Using profile URL from EventSub details: {profile_image_url}"
                    )
                    # Optimize image size for Twitch CDN URLs
                    profile_image_url = optimize_profile_image_for_notification(
                        profile_image_url
                    )

                # Priority 4: Current streamer profile URL (if HTTP)
                elif current_url and current_url.startswith("http"):
                    profile_image_url = current_url
                    logger.debug(f"Using current profile URL: {profile_image_url}")
                    # Optimize image size for Twitch CDN URLs
                    profile_image_url = optimize_profile_image_for_notification(
                        profile_image_url
                    )

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
                    logger.error("Failed to initialize notification URL")
                    return False

                # Format message using formatter
                title, message = self.formatter.format_notification_message(
                    streamer_name=streamer_name, event_type=event_type, details=details
                )

                return apprise, title, message

        except Exception as e:
            logger.error("Notification preparation failed (%s)", type(e).__name__)
            return False

    async def send_stream_notification(
        self, streamer_name: str, event_type: str, details: dict[str, object]
    ) -> bool:
        return await self._send_prepared_notification(
            self._prepare_stream_notification, streamer_name, event_type, details
        )

    async def _send_prepared_notification(
        self,
        prepare: Callable[
            [str, str, dict[str, object]], tuple[Apprise, str, str] | Literal[False]
        ],
        streamer_name: str,
        event_type: str,
        details: dict[str, object],
    ) -> bool:
        try:
            prepared = await run_in_thread_pool(
                prepare, streamer_name, event_type, details
            )
            if prepared is False:
                return False
            apprise, title, message = prepared
            return bool(
                await run_in_thread_pool(
                    apprise.notify,
                    title=title,
                    body=message,
                    body_format=NotifyFormat.TEXT,
                )
            )
        except Exception as exc:
            logger.error("Notification delivery failed (%s)", type(exc).__name__)
            return False

    async def send_test_notification(self) -> bool:
        """Send a test notification using current settings"""
        try:
            apprise = await run_in_thread_pool(self._initialize_apprise)
            if apprise is None:
                logger.error("No notification URL configured")
                return False

            result = await run_in_thread_pool(
                apprise.notify,
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
            logger.error("Test notification failed (%s)", type(e).__name__)
            return False

    def _get_service_specific_url(
        self,
        base_url: str,
        twitch_url: str,
        profile_image: str,
        streamer_name: str,
        event_type: str,
    ) -> str:
        """
        Configure service-specific parameters based on the notification service.

        IMPORTANT: profile_image must be an HTTP URL accessible by external services.
        Local file paths (/recordings/.media/...) will NOT work.
        """

        logger.debug("Configuring service-specific notification URL")

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

            params = [
                f"click={twitch_url}",
                f"priority={'high' if event_type == 'online' else 'default'}",
            ]

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
            # NOTE: For ntfy via Apprise, the URL should NOT be double-encoded
            # Apprise handles URL encoding internally
            if profile_image and profile_image.startswith("http"):
                # Don't encode the URL - Apprise handles this internally
                # Double-encoding causes the URL to become invalid
                params.append(f"avatar_url={profile_image}")  # Override Apprise icon
                params.append(
                    "image=no"
                )  # Disable automatic image attachment (prevents duplicate)
                logger.debug(
                    f"Set ntfy avatar_url to streamer profile: {profile_image}"
                )
            else:
                params.append(
                    "image=no"
                )  # Still disable image since we have no profile
                logger.debug(
                    "No valid HTTP profile image, notification will use default icon"
                )

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated ntfy notification URL")
            return final_url

        elif "discord" in base_url:
            # Discord configuration
            # avatar_url sets the webhook avatar (streamer profile pic)
            # image=yes enables image embedding in the message
            params = [f"title={title}", f"href={twitch_url}", "format=markdown"]

            # Only add avatar_url if we have a valid HTTP profile image
            # NOTE: avatar_url must be URL-encoded to properly pass special characters
            if profile_image and profile_image.startswith("http"):
                encoded_avatar_url = quote(profile_image, safe="")
                params.append(f"avatar_url={encoded_avatar_url}")
                params.append("image=yes")  # Enable image embedding
                logger.debug(
                    f"Discord notification using profile image: {profile_image}"
                )
            else:
                logger.debug(
                    "Discord notification will use default avatar (no HTTP profile image)"
                )

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated discord notification URL")
            return final_url

        elif "telegram" in base_url or "tgram" in base_url:
            # Telegram configuration
            # Use 'image' parameter with the actual URL, not just yes/no
            params = ["format=markdown"]

            if profile_image and profile_image.startswith("http"):
                # Telegram can embed images via the image parameter with URL
                encoded_image_url = quote(profile_image, safe="")
                params.append(f"image={encoded_image_url}")
                logger.debug(
                    f"Telegram notification using profile image: {profile_image}"
                )

            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug("Generated telegram notification URL")
            return final_url

        elif "matrix" in base_url:
            # Matrix configuration
            params = ["msgtype=text", "format=markdown"]

            if profile_image and profile_image.startswith("http"):
                encoded_image_url = quote(profile_image, safe="")
                params.append("thumbnail=true")
                params.append(f"image={encoded_image_url}")
                logger.debug(
                    f"Matrix notification using profile image: {profile_image}"
                )
            else:
                params.append("thumbnail=false")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated matrix notification URL")
            return final_url

        elif "slack" in base_url:
            # Slack configuration
            # Slack uses 'image' and 'thumb' parameters for embedding images
            params = ["footer=yes"]

            if profile_image and profile_image.startswith("http"):
                encoded_image_url = quote(profile_image, safe="")
                params.append("image=yes")
                params.append(f"thumb={encoded_image_url}")  # Thumbnail in attachment
                logger.debug(f"Slack notification using profile image: {profile_image}")
            else:
                params.append("image=no")

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated slack notification URL")
            return final_url

        elif "pover" in base_url:
            # Pushover configuration
            # Pushover supports image attachment via 'attachment' parameter
            params = [
                f"priority={'high' if event_type == 'online' else 'normal'}",
                f"url={twitch_url}",
                "url_title=Watch Stream",
            ]

            if profile_image and profile_image.startswith("http"):
                encoded_image_url = quote(profile_image, safe="")
                params.append(f"attachment={encoded_image_url}")
                logger.debug(
                    f"Pushover notification using profile image: {profile_image}"
                )

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated pushover notification URL")
            return final_url

        elif "gotify" in base_url:
            # Gotify configuration
            # Gotify uses 'image' parameter for embedding images
            params = [f"priority={'8' if event_type == 'online' else '5'}"]

            if profile_image and profile_image.startswith("http"):
                encoded_image_url = quote(profile_image, safe="")
                params.append(f"image={encoded_image_url}")
                logger.debug(
                    f"Gotify notification using profile image: {profile_image}"
                )

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated gotify notification URL")
            return final_url

        elif "pbul" in base_url or "pushbullet" in base_url:
            # Pushbullet configuration
            params = ["format=text"]

            if profile_image and profile_image.startswith("http"):
                encoded_image_url = quote(profile_image, safe="")
                params.append(f"image={encoded_image_url}")
                logger.debug(
                    f"Pushbullet notification using profile image: {profile_image}"
                )

            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug("Generated pushbullet notification URL")
            return final_url

        elif "msteams" in base_url or "teams" in base_url:
            # Microsoft Teams configuration
            params = []

            if profile_image and profile_image.startswith("http"):
                encoded_image_url = quote(profile_image, safe="")
                params.append(f"image={encoded_image_url}")
                logger.debug(f"Teams notification using profile image: {profile_image}")

            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug("Generated teams notification URL")
            return final_url

        # Default case - try to add avatar_url/image parameter for unknown services
        # Many Apprise services support these common parameters
        if profile_image and profile_image.startswith("http"):
            separator = "&" if "?" in base_url else "?"
            encoded_avatar_url = quote(profile_image, safe="")
            final_url = (
                f"{base_url}{separator}avatar_url={encoded_avatar_url}&image=yes"
            )
            logger.debug(
                "Using default avatar_url/image for unknown notification service"
            )
            return final_url

        logger.debug(
            "No specific configuration for this notification service, using base URL"
        )
        return base_url

    def _prepare_recording_completion(
        self,
        stream_id: int,
        output_path: str | None,
        duration_seconds: int | None,
    ) -> tuple[str, dict[str, object]] | None:
        from sqlalchemy.orm import joinedload
        from app.models import StreamerRecordingSettings

        with (self._session_factory or SessionLocal)() as db:
            stream = (
                db.query(Stream)
                .options(joinedload(Stream.streamer))
                .filter(Stream.id == stream_id)
                .first()
            )
            if stream is None or stream.streamer is None:
                return None
            path = output_path if output_path is not None else stream.recording_path
            if not path:
                return None
            policy = (
                db.query(StreamerRecordingSettings)
                .filter(StreamerRecordingSettings.streamer_id == stream.streamer_id)
                .first()
            )
            quality = (
                policy.quality if policy is not None and policy.quality else "best"
            )
            if duration_seconds is None:
                duration_seconds = (
                    int((stream.ended_at - stream.started_at).total_seconds())
                    if stream.started_at is not None and stream.ended_at is not None
                    else 0
                )
            size = os.path.getsize(path) if os.path.exists(path) else 0
            return stream.streamer.username, {
                "duration_minutes": duration_seconds // 60,
                "file_size_mb": f"{size / (1024 * 1024):.2f}",
                "quality": quality,
            }

    async def send_recording_completion(
        self,
        stream_id: int,
        *,
        output_path: str | None = None,
        duration_seconds: int | None = None,
    ) -> bool:
        prepared = await run_in_thread_pool(
            self._prepare_recording_completion, stream_id, output_path, duration_seconds
        )
        if prepared is None:
            return False
        streamer_name, details = prepared
        return await self.send_recording_notification(
            streamer_name=streamer_name,
            event_type="recording_completed",
            details=details,
        )

    def _prepare_recording_notification(
        self, streamer_name: str, event_type: str, details: dict[str, object]
    ) -> tuple[Apprise, str, str] | Literal[False]:
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
            with (self._session_factory or SessionLocal)() as db:
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
                if (
                    event_type == "recording_started"
                    and not settings.notify_recording_started
                ):
                    logger.debug("Recording started notifications disabled")
                    return False
                elif (
                    event_type == "recording_failed"
                    and not settings.notify_recording_failed
                ):
                    logger.debug("Recording failed notifications disabled")
                    return False
                elif (
                    event_type == "recording_completed"
                    and not settings.notify_recording_completed
                ):
                    logger.debug("Recording completed notifications disabled")
                    return False

                # Get streamer for profile image
                streamer = (
                    db.query(Streamer)
                    .filter(Streamer.username == streamer_name)
                    .first()
                )
                if not streamer:
                    logger.debug(f"Streamer {streamer_name} not found")
                    return False

                # Profile image URL priority:
                # 1. Locally cached image via BASE_URL (reliable, fast, always available)
                # 2. Original Twitch HTTP URL (fallback)
                # 3. EventSub details URL
                profile_image_url = ""

                # Cast SQLAlchemy columns to str for type safety
                original_url = (
                    str(streamer.original_profile_image_url)
                    if getattr(streamer, "original_profile_image_url", None)
                    else ""
                )

                # Priority 1: Use locally cached profile image if available
                local_cached_url = get_local_cached_profile_url(
                    streamer, self._settings
                )
                if local_cached_url:
                    profile_image_url = local_cached_url
                    logger.debug(
                        f"Using locally cached profile image: {profile_image_url}"
                    )
                # Priority 2: Original Twitch URL
                elif original_url and original_url.startswith("http"):
                    profile_image_url = original_url
                    profile_image_url = optimize_profile_image_for_notification(
                        profile_image_url
                    )
                # Priority 3: From notification details
                elif details and str(details.get("profile_image_url", "")).startswith(
                    "http"
                ):
                    profile_image_url = str(details["profile_image_url"])
                    profile_image_url = optimize_profile_image_for_notification(
                        profile_image_url
                    )

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
                apprise = Apprise()
                if not apprise.add(notification_url):
                    logger.error("Failed to add notification URL")
                    return False

                # Format message
                title, message = self.formatter.format_recording_notification(
                    streamer_name=streamer_name,
                    event_type=event_type,
                    details=details or {},
                )

                return apprise, title, message

        except Exception as e:
            logger.error(
                "Recording notification preparation failed (%s)", type(e).__name__
            )
            return False

    async def send_recording_notification(
        self,
        streamer_name: str,
        event_type: str,
        details: dict[str, object] | None = None,
    ) -> bool:
        return await self._send_prepared_notification(
            self._prepare_recording_notification,
            streamer_name,
            event_type,
            details or {},
        )
