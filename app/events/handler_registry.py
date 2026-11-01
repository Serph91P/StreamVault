from __future__ import annotations

import logging

import asyncio
from typing import Dict, Callable, Awaitable, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone
from cachetools import TTLCache

from app.database import SessionLocal
from app.events.event_catalog import (
    prepare_offline,
    offline_recording_id,
    prepare_online,
)
from app.utils.async_db_utils import run_in_thread_pool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.services.communication.websocket_manager import ConnectionManager
from app.services.notification_service import NotificationService
from app.services.recording.config_manager import ConfigManager
from app.services.api.twitch_api import (
    TwitchAPIService,
    twitch_api as default_twitch_api,
)
from app.models import (
    Streamer,
    Stream,
    StreamEvent,
    Category,
    User,
    FavoriteCategory,
    NotificationSettings,
    Recording,
)
from app.config.settings import Settings, settings as app_settings
from app.config.constants import CACHE_CONFIG, ASYNC_DELAYS

logger = logging.getLogger("streamvault")

if TYPE_CHECKING:
    from app.services.recording.recording_manager import RecordingManager


def get_recording_manager():
    from app.dependencies import get_recording_manager as resolve_recording_manager

    return resolve_recording_manager()


class EventHandlerRegistry:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        settings: Settings | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        recording_manager: RecordingManager | None = None,
        notification_service: NotificationService | None = None,
        twitch_api: TwitchAPIService | None = None,
    ):
        self.recording_service = recording_manager or get_recording_manager()
        self._session_factory = session_factory
        self.config_manager = ConfigManager(
            session_factory=session_factory, settings=settings
        )
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {
            "stream.online": self.handle_stream_online,
            "stream.offline": self.handle_stream_offline,
            "channel.update": self.handle_stream_update,
        }
        self.manager = connection_manager
        self.settings = settings or app_settings
        self.notification_service = notification_service or NotificationService(
            websocket_manager=connection_manager,
            session_factory=session_factory,
            settings=settings,
        )
        self.twitch_api = twitch_api or default_twitch_api

        self.eventsub = None
        # TTLCache for event deduplication (prevents memory leaks with automatic expiration)
        self._processed_events = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE,
            ttl=CACHE_CONFIG.EVENT_DEDUPLICATION_TTL,
        )

    async def get_access_token(self) -> str:
        return await self.twitch_api.get_access_token()

    async def initialize_eventsub(self):
        if self.eventsub:
            logger.debug("EventSub already initialized, skipping...")
            return

        base_url = (
            self.settings.WEBHOOK_URL if self.settings else app_settings.WEBHOOK_URL
        )
        callback_url = f"{base_url}/eventsub"
        logger.debug(f"Initializing EventSub with callback URL: {callback_url}")

        self.eventsub = {
            "callback_url": callback_url,
            "secret": self.settings.EVENTSUB_SECRET,
        }

        logger.info("EventSub initialized successfully")

    async def subscribe_to_events(self, twitch_id: str):
        if not self.eventsub:
            raise ValueError("EventSub not initialized")
        for event_type in self.handlers:
            status = await self.twitch_api.create_eventsub_subscription(
                {
                    "type": event_type,
                    "version": "2" if event_type == "channel.update" else "1",
                    "condition": {"broadcaster_user_id": twitch_id},
                    "transport": {
                        "method": "webhook",
                        "callback": self.eventsub["callback_url"],
                        "secret": self.eventsub["secret"],
                    },
                }
            )
            if status == 202:
                logger.info("Subscribed to %s for twitch_id: %s", event_type, twitch_id)
            else:
                logger.error("EventSub subscription rejected (HTTP %s)", status)

    async def verify_subscription(
        self, subscription_id: str, max_attempts: int = 10
    ) -> bool:
        await self.get_access_token()
        for _ in range(max_attempts):
            try:
                payload = await self.list_subscriptions()
                values = payload.get("data", [])
                if isinstance(values, list):
                    for sub in values:
                        if (
                            isinstance(sub, dict)
                            and sub.get("id") == subscription_id
                            and sub.get("status") == "enabled"
                        ):
                            return True
            except Exception as exc:
                logger.error("EventSub verification failed (%s)", type(exc).__name__)
            await asyncio.sleep(ASYNC_DELAYS.HANDLER_REGISTRY_RETRY)
        return False

    def is_duplicate_message(
        self,
        message_id: Optional[str],
        event_type: Optional[str],
        broadcaster_id: Optional[str],
    ) -> bool:
        """Deduplicate EventSub deliveries by Twitch message id.

        Twitch retries notifications that are not acknowledged with a 2xx in
        time; every retry reuses the same Twitch-Eventsub-Message-Id header.
        Must be called from the webhook endpoint BEFORE dispatching to a
        handler (handlers only receive the flat event payload, which does not
        contain the message id).
        """
        try:
            if not message_id:
                return False

            event_fingerprint = f"{message_id}:{event_type}:{broadcaster_id}"

            # TTLCache automatically handles expiration - no manual cleanup needed!
            if event_fingerprint in self._processed_events:
                logger.info(
                    f"Ignoring duplicate EventSub delivery: {event_type} for "
                    f"broadcaster {broadcaster_id} (message_id={message_id})"
                )
                return True

            self._processed_events[event_fingerprint] = datetime.now()
            return False

        except Exception as e:
            logger.error(f"Error checking for duplicate event: {e}", exc_info=True)
            return False

    def forget_message(
        self,
        message_id: Optional[str],
        event_type: Optional[str],
        broadcaster_id: Optional[str],
    ) -> None:
        """Remove a delivery fingerprint so a Twitch retry can be reprocessed.

        Called when handling failed (timeout/exception) and we return a non-2xx
        status: the retry must not be swallowed by the dedup cache.
        """
        try:
            self._processed_events.pop(
                f"{message_id}:{event_type}:{broadcaster_id}", None
            )
        except Exception as e:
            logger.error(f"Error forgetting event fingerprint: {e}", exc_info=True)

    async def handle_stream_online(self, data: dict):
        try:
            user_info = await self.get_user_info(data["broadcaster_user_id"])
            snapshot = await run_in_thread_pool(
                prepare_online,
                self._session_factory or SessionLocal,
                data,
                user_info,
                self.config_manager.is_recording_enabled,
            )
            if snapshot is None:
                return
            if not snapshot.new_stream:
                if snapshot.resume_recording:
                    await self.recording_service.start_recording(
                        snapshot.stream_id, snapshot.streamer_id, force_mode=False
                    )
                return
            await self.notification_service.send_stream_notification(
                streamer_name=snapshot.username,
                event_type="online",
                details={
                    "streamer_id": snapshot.streamer_id,
                    "stream_id": snapshot.stream_id,
                    "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                    "started_at": data["started_at"],
                    "title": snapshot.title,
                    "category_name": snapshot.category_name,
                    "language": snapshot.language,
                    "profile_image_url": snapshot.profile_image_url,
                    "twitch_login": data["broadcaster_user_login"],
                    "is_live": True,
                },
            )
            if await run_in_thread_pool(
                self.config_manager.is_recording_enabled, snapshot.streamer_id
            ):
                await self.recording_service.start_recording(
                    snapshot.stream_id, snapshot.streamer_id, force_mode=False
                )
        except SQLAlchemyError as e:
            logger.error(f"Database error handling stream online event: {e}")
        except Exception as e:
            logger.error(f"Error handling stream online event: {e}", exc_info=True)

    async def handle_stream_offline(self, data: dict):
        try:
            session_factory = self._session_factory or SessionLocal
            snapshot = await run_in_thread_pool(
                prepare_offline, session_factory, data["broadcaster_user_id"]
            )
            if snapshot is None:
                return
            await self.notification_service.send_stream_notification(
                streamer_name=snapshot.username,
                event_type="offline",
                details={
                    "streamer_id": snapshot.streamer_id,
                    "stream_id": snapshot.stream_id,
                    "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                    "profile_image_url": snapshot.profile_image_url,
                    "twitch_login": data["broadcaster_user_login"],
                    "is_live": False,
                },
            )
            # Read fresh after notification, preserving the existing stop ordering.
            recording_id = await run_in_thread_pool(
                offline_recording_id, session_factory, snapshot
            )
            if recording_id is not None:
                await self.recording_service.stop_recording(
                    recording_id, reason="automatic"
                )
            else:
                logger.warning(
                    "No active recording for offline streamer_id=%s stream_id=%s",
                    snapshot.streamer_id,
                    snapshot.stream_id,
                )
        except SQLAlchemyError as e:
            logger.error(f"Database error handling stream offline event: {e}")
        except Exception as e:
            logger.error(f"Error handling stream offline event: {e}", exc_info=True)

    def _resolve_event_target_stream(
        self, db: Session, streamer_id: int
    ) -> Optional[Stream]:
        """Resolve which stream a channel.update event belongs to.

        Prefer the stream that is actively being recorded — its StreamEvents
        become the chapter markers of the finished MP4. Fall back to the most
        recent still-open stream when no recording is active.
        """
        stream = (
            db.query(Stream)
            .join(Recording, Recording.stream_id == Stream.id)
            .filter(Stream.streamer_id == streamer_id)
            .filter(Recording.status == "recording")
            # A stream being actively recorded must still be open; stuck
            # status="recording" rows on ended streams (zombie recordings)
            # must not steal chapter events.
            .filter(Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .first()
        )
        if stream:
            return stream

        return (
            db.query(Stream)
            .filter(Stream.streamer_id == streamer_id)
            .filter(Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .first()
        )

    async def handle_stream_update(self, data: dict):
        try:
            logger.debug(f"Processing stream update event: {data}")
            with SessionLocal() as db:
                streamer = (
                    db.query(Streamer)
                    .filter(Streamer.twitch_id == data["broadcaster_user_id"])
                    .first()
                )

                if not streamer:
                    logger.warning(
                        f"channel.update for unknown broadcaster {data.get('broadcaster_user_id')}; ignoring"
                    )
                    return

                logger.debug(f"Found streamer: {streamer.username} (ID: {streamer.id})")
                # Resolve category name: prefer payload, else use category_id lookup
                incoming_category_name = data.get("category_name")
                category_id = data.get("category_id")
                effective_category_name = incoming_category_name
                if not effective_category_name and category_id:
                    try:
                        from app.services.streamer_service import StreamerService

                        streamer_service = StreamerService(
                            db=db,
                            websocket_manager=self.manager,
                            event_registry=self,
                        )
                        game_data = await streamer_service.get_game_data(category_id)
                        if game_data and game_data.get("name"):
                            effective_category_name = game_data.get("name")
                            logger.debug(
                                f"Resolved category name via category_id {category_id}: {effective_category_name}"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Failed to resolve category name for id {category_id}: {e}"
                        )

                streamer.title = data.get("title")
                streamer.category_name = effective_category_name
                streamer.language = data.get("language")
                streamer.last_updated = datetime.now(timezone.utc)

                db.commit()
                logger.debug(f"Updated streamer info in database: {streamer.title}")

                stream = self._resolve_event_target_stream(db, streamer.id)

                if stream:
                    # Also update the active stream with the latest title/category/language
                    try:
                        if data.get("title"):
                            stream.title = data.get("title")
                        if effective_category_name:
                            stream.category_name = effective_category_name
                        if data.get("language"):
                            stream.language = data.get("language")
                    except Exception as e:
                        logger.debug(
                            f"Could not update active stream fields from channel.update: {e}"
                        )

                    stream_event = StreamEvent(
                        stream_id=stream.id,
                        event_type="channel.update",
                        title=data.get("title"),
                        category_name=effective_category_name,
                        language=data.get("language"),
                        timestamp=datetime.now(timezone.utc),
                    )
                    db.add(stream_event)
                    db.commit()
                else:
                    logger.info(
                        f"Streamer {streamer.username} is offline, storing update for future use"
                    )

                # Send notification via notification_service - settings check handled internally
                logger.debug(
                    f"Attempting to send notification for {streamer.username}, event_type=update"
                )
                notification_result = await self.notification_service.send_stream_notification(
                    streamer_name=streamer.username,
                    event_type="update",
                    details={
                        "streamer_id": streamer.id,
                        "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                        "title": data.get("title"),
                        "category_name": effective_category_name,
                        "language": data.get("language"),
                        # Use current profile image (cached if available)
                        "profile_image_url": streamer.profile_image_url,
                        "twitch_login": data["broadcaster_user_login"],
                        "is_live": streamer.is_live,
                    },
                )
                logger.debug(f"Notification result: {notification_result}")

                logger.debug("Notifications sent successfully")
                category_name = effective_category_name
                category_id = data.get("category_id")

                if category_name and category_id:
                    from app.services.streamer_service import StreamerService

                    category = (
                        db.query(Category)
                        .filter(Category.twitch_id == category_id)
                        .first()
                    )

                    if not category:
                        # Get game data and download image immediately
                        streamer_service = StreamerService(
                            db=db, websocket_manager=self.manager, event_registry=self
                        )
                        game_data = await streamer_service.get_game_data(category_id)

                        # Create category with HTTP URL initially
                        category = Category(
                            twitch_id=category_id,
                            name=category_name
                            or (game_data.get("name") if game_data else None),
                            box_art_url=game_data.get("box_art_url")
                            if game_data
                            else None,
                        )
                        db.add(category)
                        db.commit()  # Commit first so category has an ID

                        # Now immediately download and set correct local URL
                        if game_data and game_data.get("box_art_url"):
                            try:
                                # Import the image service
                                from app.services.unified_image_service import (
                                    unified_image_service,
                                )

                                # Download the image and get local URL
                                local_url = (
                                    await unified_image_service.download_category_image(
                                        category_name, game_data.get("box_art_url")
                                    )
                                )

                                if local_url:
                                    category.box_art_url = local_url
                                    logger.info(
                                        f"Set category {category_name} image URL to: {local_url}"
                                    )

                            except Exception as img_error:
                                logger.error(
                                    f"Failed to download category image for {category_name}: {img_error}"
                                )

                    else:
                        category.name = category_name
                        category.last_seen = datetime.now(timezone.utc)

                    db.commit()

                    users_with_favorite = (
                        db.query(User)
                        .join(FavoriteCategory)
                        .filter(FavoriteCategory.category_id == category.id)
                        .all()
                    )

                    if users_with_favorite:
                        for user in users_with_favorite:
                            settings = (
                                db.query(NotificationSettings)
                                .filter(NotificationSettings.streamer_id == streamer.id)
                                .first()
                            )

                            if settings and settings.notify_favorite_category:
                                await self.notification_service.send_stream_notification(
                                    streamer_name=streamer.username,
                                    event_type="favorite_category",
                                    details={
                                        "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                                        "title": data.get("title"),
                                        "category_name": category_name,
                                        "language": data.get("language"),
                                        "profile_image_url": streamer.profile_image_url,
                                        "twitch_login": data["broadcaster_user_login"],
                                    },
                                )
        except SQLAlchemyError as e:
            logger.error(f"Database error handling stream update event: {e}")
        except Exception as e:
            logger.error(f"Error handling stream update event: {e}", exc_info=True)

    async def list_subscriptions(self) -> dict[str, object]:
        return await self.twitch_api.list_eventsub_subscriptions()

    async def delete_subscription(self, subscription_id: str) -> dict[str, str]:
        status = await self.twitch_api.delete_eventsub_subscription(subscription_id)
        if status == 204:
            return {"id": subscription_id, "status": "deleted"}
        return {
            "id": subscription_id,
            "status": "failed",
            "error": f"Status code: {status}",
        }

    async def unsubscribe_from_events(self, twitch_id: str):
        """Unsubscribe from all EventSub events for a specific streamer"""
        try:
            # Get all subscriptions
            subscriptions = await self.list_subscriptions()

            if not subscriptions or "data" not in subscriptions:
                logger.warning(
                    f"No subscriptions found to unsubscribe from for twitch_id: {twitch_id}"
                )
                return

            # Find and delete subscriptions for this broadcaster
            deleted_count = 0
            values = subscriptions["data"]
            if not isinstance(values, list):
                raise ValueError("Invalid EventSub subscription data")
            for sub in values:
                if not isinstance(sub, dict):
                    raise ValueError("Invalid EventSub subscription row")
                subscription_id = sub.get("id")
                condition = sub.get("condition", {})
                if not isinstance(subscription_id, str) or not isinstance(
                    condition, dict
                ):
                    raise ValueError("Invalid EventSub subscription identity")
                if condition.get("broadcaster_user_id") == twitch_id:
                    try:
                        await self.delete_subscription(subscription_id)
                        deleted_count += 1
                        logger.info(
                            f"Deleted subscription {sub['id']} ({sub.get('type')}) for {twitch_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to delete subscription {sub['id']}: {e}")

            if deleted_count > 0:
                logger.info(
                    f"Unsubscribed from {deleted_count} events for twitch_id: {twitch_id}"
                )
            else:
                logger.warning(f"No subscriptions found for twitch_id: {twitch_id}")

        except Exception as e:
            logger.error(
                f"Error unsubscribing from events for {twitch_id}: {e}", exc_info=True
            )
            raise

    async def delete_all_subscriptions(self):
        subs = await self.list_subscriptions()
        results = []

        values = subs.get("data", [])
        if not isinstance(values, list):
            raise ValueError("Invalid EventSub subscription data")
        for sub in values:
            if not isinstance(sub, dict) or not isinstance(sub.get("id"), str):
                raise ValueError("Invalid EventSub subscription identity")
            subscription_id = sub["id"]
            try:
                result = await self.delete_subscription(subscription_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to delete subscription {sub['id']}: {e}")
                results.append(
                    {
                        "id": sub["id"],
                        "status": "failed",
                        "error": "Failed to delete subscription",
                    }
                )

        return {"success": True, "results": results}

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user info from Twitch API including profile image"""
        try:
            users = await self.twitch_api.get_users_by_id([user_id])
            return users[0] if users else None
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            return None
