"""Streamer decisions use borrowed app adapters and complete closed DB workers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session


from app.schemas.streamers import StreamerResponse
from app.services.api.twitch_api import TwitchAPIService
from app.services.communication.websocket_manager import ConnectionManager
from app.services.streamers.streamer_repository import StreamerRepository
from app.services.streamers.twitch_integration_service import TwitchIntegrationService
from app.services.streamers.values import StreamerSnapshot, snapshot_streamer
from app.services.unified_image_service import UnifiedImageService
from app.utils.async_db_utils import run_in_thread_pool

if TYPE_CHECKING:
    from app.events.handler_registry import EventHandlerRegistry

logger = logging.getLogger("streamvault")


class StreamerService:
    """Coordinate provider, image, persistence and notification operations."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        websocket_manager: ConnectionManager,
        event_registry: EventHandlerRegistry,
        twitch_api: TwitchAPIService,
        image_service: UnifiedImageService,
    ) -> None:
        self._session_factory = session_factory
        self.manager = websocket_manager
        self.event_registry = event_registry
        self.twitch_service = TwitchIntegrationService(
            event_registry, twitch_api=twitch_api
        )
        self.twitch_api = self.twitch_service.twitch_api
        self.image_service = image_service

    async def _in_repository[T](
        self, operation: Callable[[StreamerRepository], T]
    ) -> T:
        def run() -> T:
            with self._session_factory() as db:
                return operation(StreamerRepository(db))

        return await run_in_thread_pool(run)

    async def _by_id(self, streamer_id: int) -> StreamerSnapshot | None:
        def read(repository: StreamerRepository) -> StreamerSnapshot | None:
            row = repository.get_streamer_by_id(streamer_id)
            return snapshot_streamer(row) if row is not None else None

        return await self._in_repository(read)

    async def notify(self, message: dict[str, object]) -> None:
        try:
            await self.manager.send_notification(message)
        except Exception:
            logger.warning("Streamer notification failed")
            raise

    async def get_users_by_login(self, usernames: list[str]) -> list[dict[str, object]]:
        return await self.twitch_service.get_users_by_login(usernames)

    async def get_streamer_info(self, streamer_id: str) -> dict[str, object] | None:
        return await self.twitch_service.get_streamer_info(streamer_id)

    async def get_user_data(self, username: str) -> dict[str, object] | None:
        return await self.twitch_service.get_user_data(username)

    async def get_stream_info(self, twitch_id: str) -> dict[str, object] | None:
        return await self.twitch_service.get_stream_info(twitch_id)

    async def check_streamer_live_status(self, twitch_id: str) -> bool:
        try:
            return await self.twitch_service.get_stream_info(twitch_id) is not None
        except Exception:
            logger.warning("Could not check streamer live status")
            return False

    async def get_game_data(self, game_id: str) -> dict[str, object] | None:
        return await self.twitch_service.get_game_data(game_id)

    async def subscribe_to_events(self, twitch_id: str) -> None:
        await self.twitch_service.subscribe_to_events(twitch_id)

    async def get_streamers(self) -> list[StreamerResponse]:
        return await self._in_repository(
            lambda repository: repository.get_all_streamers()
        )

    async def get_streamer_by_username(self, username: str) -> StreamerSnapshot | None:
        def read(repository: StreamerRepository) -> StreamerSnapshot | None:
            row = repository.get_streamer_by_username(username)
            return snapshot_streamer(row) if row is not None else None

        return await self._in_repository(read)

    async def download_profile_image(self, url: str, streamer_id: str) -> str:
        result = await self.image_service.download_profile_image(int(streamer_id), url)
        return result or url

    @staticmethod
    def _user_text(user_data: dict[str, object], key: str) -> str:
        value = user_data[key]
        if not isinstance(value, str):
            raise ValueError("Invalid Twitch user data")
        return value

    async def add_streamer(
        self, username: str, display_name: str | None = None
    ) -> StreamerSnapshot | None:
        try:
            user_data = await self.twitch_service.get_user_data(username)
            if not user_data:
                logger.warning("Could not fetch streamer identity")
                return None
            twitch_id = self._user_text(user_data, "id")

            def existing(repository: StreamerRepository) -> StreamerSnapshot | None:
                row = repository.get_streamer_by_twitch_id(twitch_id)
                return snapshot_streamer(row) if row is not None else None

            found = await self._in_repository(existing)
            if found is not None:
                return found
            profile_url = self._user_text(user_data, "profile_image_url")
            cached_image_path = await self.image_service.download_profile_image(
                int(twitch_id), profile_url
            )
            cached_banner_path = None
            banner_url = user_data.get("offline_image_url")
            if banner_url:
                try:
                    if not isinstance(banner_url, str):
                        raise ValueError("Invalid Twitch banner URL")
                    cached_banner_path = await self.image_service.download_banner_image(
                        int(twitch_id), banner_url
                    )
                except Exception:
                    logger.warning("Could not cache streamer banner")
            stream_info = None
            try:
                stream_info = await self.twitch_service.get_stream_info(twitch_id)
            except Exception:
                logger.warning("Could not check new streamer live status")

            def create(repository: StreamerRepository) -> StreamerSnapshot:
                return snapshot_streamer(
                    repository.create_streamer(
                        user_data=user_data,
                        display_name=display_name,
                        cached_image_path=cached_image_path or profile_url,
                        cached_banner_path=cached_banner_path,
                        stream_info=stream_info,
                    )
                )

            created = await self._in_repository(create)
            try:
                await self.twitch_service.subscribe_to_events(twitch_id)
            except Exception:
                logger.warning("Could not subscribe new streamer to EventSub")
            await self.notify(
                {"type": "success", "message": f"Added streamer {created.username}"}
            )
            return created
        except Exception:
            logger.warning("Could not add streamer")
            raise

    async def delete_streamer(self, streamer_id: int) -> dict[str, object] | None:
        row = await self._by_id(streamer_id)
        if row is None:
            return None
        try:
            await self.twitch_service.unsubscribe_from_events(row.twitch_id)
        except Exception:
            logger.warning("Could not unsubscribe removed streamer")
        result = await self._in_repository(
            lambda repository: repository.delete_streamer(streamer_id)
        )
        if result:
            await self.notify(
                {"type": "success", "message": f"Removed streamer {result['username']}"}
            )
        return result

    async def refresh_streamer_data(self, streamer_id: int) -> bool:
        try:
            row = await self._by_id(streamer_id)
            if row is None:
                return False
            user_data = await self.twitch_service.refresh_user_data(row.twitch_id)
            if not user_data:
                return False
            profile_url = user_data.get("profile_image_url")
            if profile_url != row.original_profile_image_url:
                if not isinstance(profile_url, str):
                    raise ValueError("Invalid Twitch profile URL")
                cached_path = await self.image_service.update_streamer_profile_image(
                    row.id, profile_url
                )
                if cached_path:
                    user_data["cached_profile_image"] = await run_in_thread_pool(
                        self.image_service.get_cached_profile_image, row.id
                    )
            updates = {
                "username": user_data.get("display_name", row.username),
                "profile_image_url": user_data.get("cached_profile_image", profile_url),
                "original_profile_image_url": profile_url,
            }
            description = user_data.get("description")
            if description:
                updates["description"] = description

            def update(repository: StreamerRepository) -> bool:
                current = repository.get_streamer_by_id(streamer_id)
                if current is None:
                    return False
                repository.update_streamer(current, **updates)
                return True

            return await self._in_repository(update)
        except Exception:
            logger.warning("Could not refresh streamer data")
            return False

    async def bulk_check_live_status(
        self, streamer_ids: list[int] | None = None
    ) -> dict[int, bool]:
        try:

            def read(repository: StreamerRepository) -> list[tuple[int, str]]:
                ids = (
                    streamer_ids
                    if streamer_ids
                    else [row.id for row in repository.get_all_streamers()]
                )
                rows = [repository.get_streamer_by_id(identifier) for identifier in ids]
                return [(row.id, row.twitch_id) for row in rows if row is not None]

            rows = await self._in_repository(read)
            if not rows:
                return {}
            statuses = await self.twitch_service.check_stream_status_bulk(
                [twitch_id for _, twitch_id in rows]
            )
            return {
                identifier: statuses.get(twitch_id, False)
                for identifier, twitch_id in rows
            }
        except Exception:
            logger.warning("Could not check bulk streamer status")
            return {}

    async def get_all_streamers(self) -> list[StreamerSnapshot]:
        try:
            return await self._in_repository(
                lambda repository: [
                    snapshot_streamer(row) for row in repository.get_all_streamers_raw()
                ]
            )
        except Exception:
            logger.warning("Could not read streamer identities")
            return []

    async def close(self) -> None:
        """Borrowed API/image/socket resources close with their application owner."""
