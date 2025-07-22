"""
Automatic Image Sync Service - handles background image downloading
"""
import asyncio
import logging
from typing import Optional

from app.database import SessionLocal
from app.models import Streamer, Category, Stream
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")


class AutoImageSyncService:
    """Service for automatically syncing images when entities are created/updated"""
    
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
                await asyncio.sleep(1)
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
    
    async def sync_all_existing_streamers(self):
        """Sync all existing streamers' profile images"""
        try:
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                
                count = 0
                for streamer in streamers:
                    if streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
                        await self.request_streamer_profile_sync(streamer.id, streamer.profile_image_url)
                        count += 1
                
                logger.info(f"Queued {count} streamers for profile image sync")
        except Exception as e:
            logger.error(f"Error syncing existing streamers: {e}")

    async def sync_all_existing_categories(self):
        """Sync all existing categories' images"""
        try:
            with SessionLocal() as db:
                categories = db.query(Category).all()
                
                count = 0
                for category in categories:
                    if category.box_art_url and category.box_art_url.startswith('http'):
                        await self.request_category_image_sync(category.name, category.box_art_url)
                        count += 1
                
                logger.info(f"Queued {count} categories for image sync")
        except Exception as e:
            logger.error(f"Error syncing existing categories: {e}")

    def get_queue_size(self) -> int:
        """Get the current size of the sync queue"""
        return self._sync_queue.qsize()

    def is_running(self) -> bool:
        """Check if the sync worker is running"""
        return self._running and self._sync_task is not None and not self._sync_task.done()


# Global instance
auto_image_sync_service = AutoImageSyncService()
