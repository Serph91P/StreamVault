"""
Image sync service for automatic downloading of images when entities are created/updated
"""

import asyncio
import logging
from typing import Optional, TypedDict
from collections.abc import Callable
from sqlalchemy.orm import Session
from app.utils.async_db_utils import run_in_thread_pool

from app.database import SessionLocal
from app.models import Streamer, Category
from app.services.unified_image_service import (
    UnifiedImageService,
    unified_image_service,
)
from app.config.constants import ASYNC_DELAYS, TIMEOUTS

logger = logging.getLogger("streamvault")


class SyncRequest(TypedDict, total=False):
    type: str
    streamer_id: int
    stream_id: int
    profile_image_url: str
    category_name: str
    image_url: str | None
    artwork_url: str


class ImageSyncService:
    """Service for automatically syncing images when entities are created/updated"""

    def __init__(
        self,
        *,
        image_service: UnifiedImageService | None = None,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._image_service = image_service
        self._session_factory = session_factory
        self._sync_queue: asyncio.Queue[SyncRequest] = asyncio.Queue()
        self._sync_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def _images(self) -> UnifiedImageService:
        return self._image_service or unified_image_service

    async def start_sync_worker(self) -> None:
        """Start the background sync worker"""
        if self._sync_task is None or self._sync_task.done():
            self._running = True
            self._sync_task = asyncio.create_task(self._sync_worker())
            logger.info("Image sync worker started")

    async def stop_sync_worker(self) -> None:
        """Stop the background sync worker"""
        self._running = False
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Image sync worker stopped")

    async def _sync_worker(self) -> None:
        """Background worker that processes sync requests"""
        logger.info("Image sync background worker started")
        while self._running:
            try:
                # Wait for sync request with timeout to check _running periodically
                sync_request = await asyncio.wait_for(
                    self._sync_queue.get(), timeout=TIMEOUTS.IMAGE_SYNC_QUEUE_TIMEOUT
                )
                try:
                    await self._process_sync_request(sync_request)
                    await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_REQUEST_DELAY)
                finally:
                    self._sync_queue.task_done()

            except asyncio.TimeoutError:
                continue  # Check if still running
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in image sync worker: {e}")
                await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_WORKER_ERROR_WAIT)
        logger.info("Image sync background worker stopped")

    async def _process_sync_request(self, sync_request: SyncRequest) -> None:
        """Process a single sync request"""
        try:
            request_type = sync_request.get("type")

            if request_type == "streamer_profile":
                await self._sync_streamer_profile(sync_request)
            elif request_type == "category_image":
                await self._sync_category_image(sync_request)
            elif request_type == "stream_artwork":
                await self._sync_stream_artwork(sync_request)
            else:
                logger.warning(f"Unknown sync request type: {request_type}")

        except Exception as e:
            logger.error(f"Error processing sync request {sync_request}: {e}")

    async def _sync_streamer_profile(self, sync_request: SyncRequest) -> None:
        """Sync a streamer's profile image"""
        streamer_id = sync_request.get("streamer_id")
        profile_image_url = sync_request.get("profile_image_url")

        if streamer_id and profile_image_url:
            logger.info(f"Syncing profile image for streamer {streamer_id}")
            await self._images.download_profile_image(streamer_id, profile_image_url)

    async def _sync_category_image(self, sync_request: SyncRequest) -> None:
        """Sync a category image"""
        category_name = sync_request.get("category_name")
        image_url = sync_request.get("image_url")

        if category_name:
            logger.info(f"Syncing category image for {category_name}")
            if image_url:
                await self._images.download_category_image(category_name, image_url)
            else:
                await self._images.download_category_image(category_name, "")

    async def _sync_stream_artwork(self, sync_request: SyncRequest) -> None:
        """Sync stream artwork"""
        stream_id = sync_request.get("stream_id")
        streamer_id = sync_request.get("streamer_id")
        artwork_url = sync_request.get("artwork_url")

        if stream_id and streamer_id and artwork_url:
            logger.info(f"Syncing stream artwork for stream {stream_id}")
            await self._images.download_stream_artwork(
                stream_id, streamer_id, artwork_url
            )

    # Public methods for requesting syncs

    async def request_streamer_profile_sync(
        self, streamer_id: int, profile_image_url: str
    ) -> None:
        """Request sync of a streamer's profile image"""
        await self._sync_queue.put(
            {
                "type": "streamer_profile",
                "streamer_id": streamer_id,
                "profile_image_url": profile_image_url,
            }
        )

    async def request_category_image_sync(
        self, category_name: str, image_url: Optional[str] = None
    ) -> None:
        """Request sync of a category image"""
        await self._sync_queue.put(
            {
                "type": "category_image",
                "category_name": category_name,
                "image_url": image_url,
            }
        )

    async def request_stream_artwork_sync(
        self, stream_id: int, streamer_id: int, artwork_url: str
    ) -> None:
        """Request sync of stream artwork"""
        await self._sync_queue.put(
            {
                "type": "stream_artwork",
                "stream_id": stream_id,
                "streamer_id": streamer_id,
                "artwork_url": artwork_url,
            }
        )

    # Bulk sync operations

    def _profile_sources(self) -> list[tuple[int, str | None]]:
        with (self._session_factory or SessionLocal)() as db:
            return [
                (row.id, row.original_profile_image_url or row.profile_image_url)
                for row in db.query(
                    Streamer.id,
                    Streamer.original_profile_image_url,
                    Streamer.profile_image_url,
                ).all()
            ]

    def _category_names(self, names: list[str] | None = None) -> list[str]:
        with (self._session_factory or SessionLocal)() as db:
            query = db.query(Category.name)
            if names is not None:
                query = query.filter(Category.name.in_(names))
            return [row.name for row in query.all()]

    async def sync_all_existing_streamers(self) -> None:
        """Sync all existing streamers' profile images"""
        try:
            sources = await run_in_thread_pool(self._profile_sources)
            for streamer_id, source in sources:
                if source:
                    await self.request_streamer_profile_sync(streamer_id, source)
            logger.info(f"Requested sync for {len(sources)} streamers")

        except Exception as e:
            logger.error(f"Error syncing all existing streamers: {e}")

    async def sync_all_existing_categories(self) -> None:
        """Sync all existing categories' images"""
        try:
            names = await run_in_thread_pool(self._category_names)
            for name in names:
                if name:
                    await self.request_category_image_sync(name)
            logger.info(f"Requested sync for {len(names)} categories")

        except Exception as e:
            logger.error(f"Error syncing all existing categories: {e}")

    async def sync_popular_categories_only(self) -> None:
        """Sync only popular categories to avoid rate limiting"""
        try:
            # Popular categories that are commonly used
            popular_categories = [
                "Just Chatting",
                "League of Legends",
                "Fortnite",
                "Minecraft",
                "Grand Theft Auto V",
                "Valorant",
                "Counter-Strike 2",
                "World of Warcraft",
                "Dota 2",
                "Apex Legends",
                "Call of Duty: Modern Warfare III",
                "Rocket League",
                "Overwatch 2",
                "Hearthstone",
                "Among Us",
                "Fall Guys",
                "PUBG: BATTLEGROUNDS",
                "Dead by Daylight",
                "Escape from Tarkov",
                "Path of Exile",
            ]

            # Only sync categories that exist in the database
            names = await run_in_thread_pool(self._category_names, popular_categories)
            for name in names:
                if name:
                    await self.request_category_image_sync(name)

            logger.info(f"Requested sync for {len(names)} popular categories")

        except Exception as e:
            logger.error(f"Error syncing popular categories: {e}")

    def get_queue_size(self) -> int:
        """Get the current size of the sync queue"""
        return self._sync_queue.qsize()

    def is_running(self) -> bool:
        """Check if the sync worker is running"""
        return self._sync_task is not None and not self._sync_task.done()

    async def _initial_sync(self) -> None:
        """Perform initial sync of all existing streamers and categories"""
        try:
            logger.info("Starting initial image sync for all existing entities...")

            # Sync all existing streamers
            await self.sync_all_existing_streamers()

            # Sync all existing categories
            await self.sync_all_existing_categories()

            logger.info("Initial image sync completed")
        except Exception as e:
            logger.error(f"Error during initial image sync: {e}")

    async def _initial_sync_delayed(self) -> None:
        """Perform initial sync after a short delay (non-blocking startup)"""
        try:
            # Wait longer to allow startup to complete
            await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_INTERVAL)

            logger.info(
                "Starting delayed initial image sync for all existing entities..."
            )

            # Sync all existing streamers first (fewer API calls)
            await self.sync_all_existing_streamers()

            # For categories, only sync a limited number to avoid rate limiting
            await self.sync_popular_categories_only()

            logger.info("Delayed initial image sync completed")
        except Exception as e:
            logger.error(f"Error during delayed initial image sync: {e}")

    def _missing_sources(self) -> tuple[list[tuple[int, str]], list[str]]:
        profiles = [
            (streamer_id, source)
            for streamer_id, source in self._profile_sources()
            if source and not self._images.get_cached_profile_image(streamer_id)
        ]
        names = [
            name
            for name in self._category_names()
            if name and not self._images.get_cached_category_image(name)
        ]
        return profiles, names

    async def check_and_sync_missing_images(self) -> None:
        """Enqueue absent files from closed worker-owned source snapshots."""
        try:
            profiles, names = await run_in_thread_pool(self._missing_sources)
            for streamer_id, source in profiles:
                await self.request_streamer_profile_sync(streamer_id, source)
            for name in names:
                await self.request_category_image_sync(name)
            if profiles or names:
                logger.info(
                    "Requested sync for %d missing profiles and %d categories",
                    len(profiles),
                    len(names),
                )
            else:
                logger.info("All images are up to date")
        except Exception as e:
            logger.error(f"Error checking for missing images: {e}")


# Global instance
image_sync_service = ImageSyncService()
