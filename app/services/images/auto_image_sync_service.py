"""
Automatic Image Sync Service - handles background image downloading
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.database import SessionLocal
from app.models import Streamer, Category
from app.services.unified_image_service import unified_image_service
from app.config.constants import ASYNC_DELAYS

logger = logging.getLogger("streamvault")


class AutoImageSyncService:
    """Service for automatically syncing images when entities are created/updated"""

    # Configuration constants
    PROFILES_BASE_PATH = "/recordings/.media/profiles/"
    TWITCH_PROFILE_URL_TEMPLATE = "https://static-cdn.jtvnw.net/jtv_user_pictures/{twitch_id}-profile_image-300x300.png"

    def __init__(self):
        self._sync_queue = asyncio.Queue()
        self._sync_task = None
        self._running = False

    async def start_sync_worker(self):
        """Start the background sync worker"""
        if self._sync_task is None or self._sync_task.done():
            self._running = True
            self._sync_task = asyncio.create_task(self._sync_worker())
            logger.info("Auto image sync worker started")

    async def stop_sync_worker(self):
        """Stop the background sync worker"""
        self._running = False
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto image sync worker stopped")

    async def _sync_worker(self):
        """Background worker that processes sync requests"""
        logger.info("Auto image sync background worker started")
        while self._running:
            try:
                # Wait for sync request with timeout to check _running periodically
                sync_request = await asyncio.wait_for(self._sync_queue.get(), timeout=5.0)
                await self._process_sync_request(sync_request)
            except asyncio.TimeoutError:
                continue  # Check if still running
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto image sync worker: {e}")
                await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_WORKER_ERROR_WAIT)
        logger.info("Auto image sync background worker stopped")

    async def _process_sync_request(self, sync_request: dict):
        """Process a single sync request"""
        try:
            sync_type = sync_request.get("type")
            if sync_type == "streamer_profile":
                await self._sync_streamer_profile(sync_request)
            elif sync_type == "category_image":
                await self._sync_category_image(sync_request)
            elif sync_type == "stream_artwork":
                await self._sync_stream_artwork(sync_request)
            else:
                logger.warning(f"Unknown sync request type: {sync_type}")
        except Exception as e:
            logger.error(f"Error processing sync request {sync_request}: {e}")

    async def _sync_streamer_profile(self, sync_request: dict):
        """Sync a streamer's profile image"""
        streamer_id = sync_request.get("streamer_id")
        profile_image_url = sync_request.get("profile_image_url")

        if streamer_id and profile_image_url:
            try:
                cached_path = await unified_image_service.download_profile_image(streamer_id, profile_image_url)
                if cached_path:
                    logger.info(f"Successfully synced profile image for streamer {streamer_id}")

                    # Update database with cached path
                    with SessionLocal() as db:
                        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                        if streamer:
                            streamer.profile_image_url = cached_path
                            db.commit()
                else:
                    logger.warning(f"Failed to sync profile image for streamer {streamer_id}")
            except Exception as e:
                logger.error(f"Error syncing profile image for streamer {streamer_id}: {e}")

    async def _sync_category_image(self, sync_request: dict):
        """Sync a category image"""
        category_name = sync_request.get("category_name")
        image_url = sync_request.get("image_url")

        if category_name:
            try:
                # Get image URL from database if not provided
                if not image_url:
                    with SessionLocal() as db:
                        category = db.query(Category).filter(Category.name == category_name).first()
                        if category and category.box_art_url:
                            image_url = category.box_art_url

                if image_url and image_url.startswith('http'):
                    cached_path = await unified_image_service.download_category_image(category_name, image_url)
                    if cached_path:
                        logger.info(f"Successfully synced category image for {category_name}")

                        # Update database with cached path
                        with SessionLocal() as db:
                            category = db.query(Category).filter(Category.name == category_name).first()
                            if category:
                                category.box_art_url = cached_path
                                db.commit()
                    else:
                        logger.warning(f"Failed to sync category image for {category_name}")
                else:
                    logger.debug(f"No valid image URL for category {category_name}")
            except Exception as e:
                logger.error(f"Error syncing category image for {category_name}: {e}")

    async def _sync_stream_artwork(self, sync_request: dict):
        """Sync stream artwork"""
        stream_id = sync_request.get("stream_id")
        streamer_id = sync_request.get("streamer_id")
        artwork_url = sync_request.get("artwork_url")

        if stream_id and streamer_id and artwork_url:
            try:
                cached_path = await unified_image_service.download_stream_artwork(stream_id, streamer_id, artwork_url)
                if cached_path:
                    logger.info(f"Successfully synced stream artwork for stream {stream_id}")
                else:
                    logger.warning(f"Failed to sync stream artwork for stream {stream_id}")
            except Exception as e:
                logger.error(f"Error syncing stream artwork for stream {stream_id}: {e}")

    # Public methods for requesting syncs

    async def request_streamer_profile_sync(self, streamer_id: int, profile_image_url: str):
        """Request sync of a streamer's profile image"""
        await self._sync_queue.put({
            "type": "streamer_profile",
            "streamer_id": streamer_id,
            "profile_image_url": profile_image_url
        })

    async def request_category_image_sync(self, category_name: str, image_url: Optional[str] = None):
        """Request sync of a category image"""
        await self._sync_queue.put({
            "type": "category_image",
            "category_name": category_name,
            "image_url": image_url
        })

    async def request_stream_artwork_sync(self, stream_id: int, streamer_id: int, artwork_url: str):
        """Request sync of stream artwork"""
        await self._sync_queue.put({
            "type": "stream_artwork",
            "stream_id": stream_id,
            "streamer_id": streamer_id,
            "artwork_url": artwork_url
        })

    # Bulk sync operations

    async def sync_all_existing_streamers(self, limit: int = 100, offset: int = 0):
        """Sync existing streamers' profile images (with pagination)

        Args:
            limit: Maximum number of streamers to process in this batch
            offset: Number of streamers to skip (for pagination)

        Note: For syncing all streamers, use sync_all_streamers_paginated() instead
        to avoid memory issues with large datasets.
        """
        try:
            with SessionLocal() as db:
                # Query all streamers to check if they need profile image syncing
                streamers = db.query(Streamer).limit(limit).offset(offset).all()

                count = 0
                for streamer in streamers:
                    needs_sync = False

                    # Check if streamer has HTTP URL (needs downloading)
                    if streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
                        needs_sync = True
                    # Check if streamer has local path but file doesn't exist (needs re-downloading)
                    elif streamer.profile_image_url and streamer.profile_image_url.startswith('/data/images/'):
                        # Check if the local file actually exists
                        filename = Path(streamer.profile_image_url).name
                        local_file_path = Path(self.PROFILES_BASE_PATH) / filename
                        if not local_file_path.exists():
                            # File is missing, force to use the default Twitch avatar URL template
                            logger.warning(f"Profile image file missing for streamer {streamer.username}: {streamer.profile_image_url}")
                            logger.info(f"Expected file at: {local_file_path}")
                            # Use Twitch's default profile image URL pattern
                            twitch_profile_url = self.TWITCH_PROFILE_URL_TEMPLATE.format(twitch_id=streamer.twitch_id)
                            needs_sync = True
                            # Temporarily update the URL for download
                            streamer.profile_image_url = twitch_profile_url
                        else:
                            logger.info(f"Profile image exists for {streamer.username}: {local_file_path}")

                    if needs_sync:
                        await self.request_streamer_profile_sync(streamer.id, streamer.profile_image_url)
                        count += 1

                logger.info(f"Queued {count} streamers for profile image sync (batch: offset={offset}, limit={limit})")
                return count  # Return count for pagination logic
        except Exception as e:
            logger.error(f"Error syncing existing streamers: {e}")
            return 0

    async def sync_all_existing_categories(self, limit: int = 100, offset: int = 0):
        """Sync existing categories' images (with pagination)

        Args:
            limit: Maximum number of categories to process in this batch
            offset: Number of categories to skip (for pagination)

        Note: For syncing all categories, use sync_all_categories_paginated() instead
        to avoid memory issues with large datasets.
        """
        try:
            with SessionLocal() as db:
                # Only query categories that have HTTP URLs and need syncing
                categories = db.query(Category).filter(
                    Category.box_art_url.ilike('http%')
                ).limit(limit).offset(offset).all()

                count = 0
                for category in categories:
                    await self.request_category_image_sync(category.name, category.box_art_url)
                    count += 1

                logger.info(f"Queued {count} categories for image sync (batch: offset={offset}, limit={limit})")
                return count  # Return count for pagination logic
        except Exception as e:
            logger.error(f"Error syncing existing categories: {e}")
            return 0

    async def sync_all_streamers_paginated(self, batch_size: int = 100):
        """Sync all streamers using pagination to avoid memory issues"""
        total_synced = 0
        offset = 0

        while True:
            batch_count = await self.sync_all_existing_streamers(limit=batch_size, offset=offset)
            total_synced += batch_count

            if batch_count < batch_size:
                # No more streamers to process
                break

            offset += batch_size
            # Small delay to prevent overwhelming the database
            await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_BATCH_DELAY)

        logger.info(f"Completed sync for {total_synced} streamers total")
        return total_synced

    async def sync_all_categories_paginated(self, batch_size: int = 100):
        """Sync all categories using pagination to avoid memory issues"""
        total_synced = 0
        offset = 0

        while True:
            batch_count = await self.sync_all_existing_categories(limit=batch_size, offset=offset)
            total_synced += batch_count

            if batch_count < batch_size:
                # No more categories to process
                break

            offset += batch_size
            # Small delay to prevent overwhelming the database
            await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_BATCH_DELAY)

        logger.info(f"Completed sync for {total_synced} categories total")
        return total_synced

    def get_queue_size(self) -> int:
        """Get the current size of the sync queue"""
        return self._sync_queue.qsize()

    def is_running(self) -> bool:
        """Check if the sync worker is running"""
        return self._running and self._sync_task is not None and not self._sync_task.done()


# Global instance
auto_image_sync_service = AutoImageSyncService()
