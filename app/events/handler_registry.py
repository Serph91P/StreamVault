from __future__ import annotations

import logging

import asyncio
from typing import Dict, Callable, Awaitable, Any, Optional, TYPE_CHECKING
from datetime import datetime
from cachetools import TTLCache

from app.database import SessionLocal
from app.events.event_catalog import (
    prepare_offline,
    offline_recording_id,
    prepare_online,
    update_broadcaster_exists,
    prepare_update,
    update_category_exists,
    prepare_update_category,
    publish_update_category_image,
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
    Stream,
    Recording,
)
from app.config.settings import Settings, settings as app_settings
from app.config.constants import CACHE_CONFIG, ASYNC_DELAYS

logger = logging.getLogger("streamvault")

if TYPE_CHECKING:
    from app.services.recording.recording_manager import RecordingManager
    from app.services.unified_image_service import UnifiedImageService


def get_recording_manager() -> RecordingManager:
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
        image_service: UnifiedImageService | None = None,
    ):
        self.recording_service = recording_manager or get_recording_manager()
        self._session_factory = session_factory
        self._image_service = image_service
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

        self.eventsub: dict[str, str | None] | None = None
        # TTLCache for event deduplication (prevents memory leaks with automatic expiration)
        self._processed_events: TTLCache[str, datetime] = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE,
            ttl=CACHE_CONFIG.EVENT_DEDUPLICATION_TTL,
        )

    async def get_access_token(self) -> str:
        return await self.twitch_api.get_access_token()

    async def initialize_eventsub(self) -> None:
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

    async def subscribe_to_events(self, twitch_id: str) -> None:
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

    async def handle_stream_online(self, data: dict[str, str]) -> None:
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

    async def handle_stream_offline(self, data: dict[str, str]) -> None:
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

    async def handle_stream_update(self, data: dict[str, str]) -> None:
        sessions = self._session_factory or SessionLocal
        try:
            if not await run_in_thread_pool(
                update_broadcaster_exists, sessions, data["broadcaster_user_id"]
            ):
                logger.warning("channel.update for unknown broadcaster; ignoring")
                return
            category_name, category_id = (
                data.get("category_name"),
                data.get("category_id"),
            )
            game_data = None
            if not category_name and category_id:
                try:
                    games = await self.twitch_api.get_games_by_id([category_id])
                    game_data = games[0] if games else None
                    name = game_data.get("name") if game_data else None
                    if isinstance(name, str):
                        category_name = name
                except Exception as error:
                    logger.debug(
                        "Category name lookup failed (%s)", type(error).__name__
                    )
            snapshot = await run_in_thread_pool(
                prepare_update,
                sessions,
                data,
                category_name,
                self._resolve_event_target_stream,
            )
            if snapshot is None:
                return
            details = {
                "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                "title": data.get("title"),
                "category_name": category_name,
                "language": data.get("language"),
                "profile_image_url": snapshot.profile_image_url,
                "twitch_login": data["broadcaster_user_login"],
            }
            await self.notification_service.send_stream_notification(
                streamer_name=snapshot.username,
                event_type="update",
                details={
                    **details,
                    "streamer_id": snapshot.streamer_id,
                    "is_live": snapshot.is_live,
                },
            )
            if category_name and category_id:
                exists = await run_in_thread_pool(
                    update_category_exists, sessions, category_id
                )
                if not exists and game_data is None:
                    games = await self.twitch_api.get_games_by_id([category_id])
                    game_data = games[0] if games else None
                source = game_data.get("box_art_url") if game_data else None
                source = source if isinstance(source, str) else None
                identity, favorite_count = await run_in_thread_pool(
                    prepare_update_category,
                    sessions,
                    category_id,
                    category_name,
                    source,
                    snapshot.streamer_id,
                )
                if not exists and source:
                    try:
                        image_service = self._image_service
                        if image_service is None:
                            from app.services.unified_image_service import (
                                unified_image_service,
                            )

                            image_service = unified_image_service
                        local_url = await image_service.download_category_image(
                            category_name, source
                        )
                        if local_url:
                            await run_in_thread_pool(
                                publish_update_category_image,
                                sessions,
                                identity,
                                local_url,
                            )
                    except Exception as error:
                        logger.error(
                            "Category image download failed (%s)", type(error).__name__
                        )
                for _ in range(favorite_count):
                    await self.notification_service.send_stream_notification(
                        streamer_name=snapshot.username,
                        event_type="favorite_category",
                        details=dict(details),
                    )
        except SQLAlchemyError as error:
            logger.error(
                "Database error handling stream update (%s)", type(error).__name__
            )
        except Exception as error:
            logger.error("Error handling stream update (%s)", type(error).__name__)

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

    async def unsubscribe_from_events(self, twitch_id: str) -> None:
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

    async def delete_all_subscriptions(self) -> dict[str, object]:
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
