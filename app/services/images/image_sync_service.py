"""
Image sync service for automatic downloading of images when entities are created/updated
"""
import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Streamer, Category, Stream
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")

class ImageSyncService:
    """Service for automatically syncing images when entities are created/updated"""
    
    def __init__(self):
        self._sync_queue = asyncio.Queue()
        self._sync_task = None
        
    async def start_sync_worker(self):
        """Start the background sync worker"""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._sync_worker())
            logger.info("Image sync worker started")
            
            # Schedule initial sync as background task (non-blocking)
            asyncio.create_task(self._initial_sync_delayed())
    
    async def stop_sync_worker(self):
        """Stop the background sync worker"""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            logger.info("Image sync worker stopped")
    
    async def _sync_worker(self):
        """Background worker that processes sync requests"""
        while True:
            try:
                # Get next sync request
                sync_request = await self._sync_queue.get()
                
                # Process the sync request
                await self._process_sync_request(sync_request)
                
                # Add delay between requests to avoid rate limiting
                await asyncio.sleep(0.5)  # 500ms delay between requests
                
                # Mark task as done
                self._sync_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in image sync worker: {e}")
                await asyncio.sleep(5)  # Wait before continuing
    
    async def _process_sync_request(self, sync_request: dict):
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
    
    async def _sync_streamer_profile(self, sync_request: dict):
        """Sync a streamer's profile image"""
        streamer_id = sync_request.get("streamer_id")
        profile_image_url = sync_request.get("profile_image_url")
        
        if streamer_id and profile_image_url:
            logger.info(f"Syncing profile image for streamer {streamer_id}")
            await unified_image_service.download_profile_image(streamer_id, profile_image_url)
    
    async def _sync_category_image(self, sync_request: dict):
        """Sync a category image"""
        category_name = sync_request.get("category_name")
        image_url = sync_request.get("image_url")
        
        if category_name:
            logger.info(f"Syncing category image for {category_name}")
            await unified_image_service.download_category_image(category_name, image_url)
    
    async def _sync_stream_artwork(self, sync_request: dict):
        """Sync stream artwork"""
        stream_id = sync_request.get("stream_id")
        streamer_id = sync_request.get("streamer_id")
        artwork_url = sync_request.get("artwork_url")
        
        if stream_id and streamer_id and artwork_url:
            logger.info(f"Syncing stream artwork for stream {stream_id}")
            await unified_image_service.download_stream_artwork(stream_id, streamer_id, artwork_url)
    
    # Public methods for requesting syncs
    
    async def request_streamer_profile_sync(self, streamer_id: int, profile_image_url: str):
        """Request sync of a streamer's profile image"""
        await self._sync_queue.put({
            "type": "streamer_profile",
            "streamer_id": streamer_id,
            "profile_image_url": profile_image_url
        })
    
    async def request_category_image_sync(self, category_name: str, image_url: str = None):
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
                
            for streamer in streamers:
                if streamer.profile_image_url:
                    await self.request_streamer_profile_sync(
                        streamer.id, 
                        streamer.profile_image_url
                    )
                    
            logger.info(f"Requested sync for {len(streamers)} streamers")
            
        except Exception as e:
            logger.error(f"Error syncing all existing streamers: {e}")
    
    async def sync_all_existing_categories(self):
        """Sync all existing categories' images"""
        try:
            with SessionLocal() as db:
                categories = db.query(Category).all()
                
            for category in categories:
                if category.name:
                    await self.request_category_image_sync(category.name)
                    
            logger.info(f"Requested sync for {len(categories)} categories")
            
        except Exception as e:
            logger.error(f"Error syncing all existing categories: {e}")
    
    async def sync_popular_categories_only(self):
        """Sync only popular categories to avoid rate limiting"""
        try:
            # Popular categories that are commonly used
            popular_categories = [
                'Just Chatting',
                'League of Legends',
                'Fortnite',
                'Minecraft',
                'Grand Theft Auto V',
                'Valorant',
                'Counter-Strike 2',
                'World of Warcraft',
                'Dota 2',
                'Apex Legends',
                'Call of Duty: Modern Warfare III',
                'Rocket League',
                'Overwatch 2',
                'Hearthstone',
                'Among Us',
                'Fall Guys',
                'PUBG: BATTLEGROUNDS',
                'Dead by Daylight',
                'Escape from Tarkov',
                'Path of Exile'
            ]
            
            # Only sync categories that exist in the database
            with SessionLocal() as db:
                existing_categories = db.query(Category).filter(
                    Category.name.in_(popular_categories)
                ).all()
                
            for category in existing_categories:
                if category.name:
                    await self.request_category_image_sync(category.name)
                    
            logger.info(f"Requested sync for {len(existing_categories)} popular categories")
            
        except Exception as e:
            logger.error(f"Error syncing popular categories: {e}")
    
    def get_queue_size(self) -> int:
        """Get the current size of the sync queue"""
        return self._sync_queue.qsize()
    
    def is_running(self) -> bool:
        """Check if the sync worker is running"""
        return self._sync_task is not None and not self._sync_task.done()
    
    async def _initial_sync(self):
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
    
    async def _initial_sync_delayed(self):
        """Perform initial sync after a short delay (non-blocking startup)"""
        try:
            # Wait longer to allow startup to complete
            await asyncio.sleep(30)
            
            logger.info("Starting delayed initial image sync for all existing entities...")
            
            # Sync all existing streamers first (fewer API calls)
            await self.sync_all_existing_streamers()
            
            # For categories, only sync a limited number to avoid rate limiting
            await self.sync_popular_categories_only()
            
            logger.info("Delayed initial image sync completed")
        except Exception as e:
            logger.error(f"Error during delayed initial image sync: {e}")
    
    async def check_and_sync_missing_images(self):
        """Check for missing images and sync them"""
        try:
            logger.info("Checking for missing images...")
            
            # Check streamers
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                
            missing_profiles = 0
            for streamer in streamers:
                if streamer.profile_image_url:
                    cached_url = unified_image_service.get_profile_image_url(streamer.id)
                    # If cached_url is the same as original URL, it means no cached version exists
                    if cached_url == streamer.profile_image_url:
                        await self.request_streamer_profile_sync(streamer.id, streamer.profile_image_url)
                        missing_profiles += 1
            
            # Check categories
            with SessionLocal() as db:
                categories = db.query(Category).all()
                
            missing_categories = 0
            for category in categories:
                if category.name:
                    cached_url = unified_image_service.get_category_image_url(category.name)
                    # If no cached image exists, sync it
                    if not cached_url or cached_url == unified_image_service.get_category_image_url(category.name):
                        await self.request_category_image_sync(category.name)
                        missing_categories += 1
            
            if missing_profiles > 0 or missing_categories > 0:
                logger.info(f"Requested sync for {missing_profiles} missing profile images and {missing_categories} missing category images")
            else:
                logger.info("All images are up to date")
                
        except Exception as e:
            logger.error(f"Error checking for missing images: {e}")

# Global instance
image_sync_service = ImageSyncService()
