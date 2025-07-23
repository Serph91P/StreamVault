"""
Image Refresh Service

Handles automatic re-downloading of missing images and frontend integration.
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Streamer, Category, Stream
from app.services.unified_image_service import unified_image_service
from app.utils.file_utils import sanitize_filename
from app.utils.async_db_utils import get_async_session

logger = logging.getLogger("streamvault")

class ImageRefreshService:
    """Service for checking and re-downloading missing images"""
    
    def __init__(self):
        # Hardcoded Docker path - always /recordings in container
        self.recordings_dir = Path("/recordings")
        self.media_dir = self.recordings_dir / ".media"
        
    async def check_and_refresh_missing_images(self) -> Dict[str, int]:
        """Check for missing images and re-download them"""
        stats = {
            "profile_images_refreshed": 0,
            "category_images_refreshed": 0,
            "stream_artwork_refreshed": 0,
            "errors": 0
        }
        
        try:
            # Check profile images
            profile_stats = await self._refresh_missing_profile_images()
            stats["profile_images_refreshed"] = profile_stats["refreshed"]
            stats["errors"] += profile_stats["errors"]
            
            # Check category images  
            category_stats = await self._refresh_missing_category_images()
            stats["category_images_refreshed"] = category_stats["refreshed"]
            stats["errors"] += category_stats["errors"]
            
            # Check stream artwork
            artwork_stats = await self._refresh_missing_stream_artwork()
            stats["stream_artwork_refreshed"] = artwork_stats["refreshed"]
            stats["errors"] += artwork_stats["errors"]
            
            logger.info(f"Image refresh completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during image refresh: {e}")
            stats["errors"] += 1
            return stats
    
    async def _refresh_missing_profile_images(self) -> Dict[str, int]:
        """Check and refresh missing profile images"""
        stats = {"refreshed": 0, "errors": 0}
        
        try:
            from app.utils.async_db_utils import get_all_streamers, batch_process_items
            streamers = await get_all_streamers()
            
            # Process streamers in batches for better performance
            async for batch in batch_process_items(streamers, batch_size=10, max_concurrent=3):
                batch_tasks = []
                for streamer in batch:
                    if streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
                        # Check if cached file exists (try both old and new naming)
                        expected_path_new = self.media_dir / "profiles" / f"profile_avatar_{streamer.id}.jpg"
                        expected_path_old = self.media_dir / "profiles" / f"streamer_{streamer.id}.jpg"
                        
                        if not expected_path_new.exists() and not expected_path_old.exists():
                            logger.info(f"Profile image missing for streamer {streamer.id}, re-downloading...")
                            task = self._download_profile_image(streamer)
                            batch_tasks.append(task)
                
                # Process batch concurrently
                if batch_tasks:
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.error(f"Error in batch profile image download: {result}")
                            stats["errors"] += 1
                        elif result:
                            stats["refreshed"] += 1
                
        except Exception as e:
            logger.error(f"Error refreshing profile images: {e}")
            stats["errors"] += 1
            
        return stats
    
    async def _download_profile_image(self, streamer: Streamer) -> bool:
        """Download profile image for a single streamer"""
        try:
            cached_path = await unified_image_service.download_profile_image(
                streamer.id, 
                streamer.profile_image_url
            )
            if cached_path:
                # Update database with cached path using proper session
                from app.utils.async_db_utils import get_async_session
                async with get_async_session() as db:
                    # Re-fetch the streamer in this session context
                    stmt = select(Streamer).where(Streamer.id == streamer.id)
                    result = await db.execute(stmt)
                    db_streamer = result.scalar_one_or_none()
                    
                    if db_streamer:
                        db_streamer.profile_image_url = cached_path
                        await db.commit()
                        logger.info(f"Successfully refreshed profile image for streamer {streamer.id}")
                        return True
                    else:
                        logger.warning(f"Streamer {streamer.id} not found in database")
                        return False
            else:
                logger.warning(f"Failed to download profile image for streamer {streamer.id}")
                return False
        except Exception as e:
            logger.error(f"Error refreshing profile image for streamer {streamer.id}: {e}")
            return False
    
    async def _refresh_missing_category_images(self) -> Dict[str, int]:
        """Check and refresh missing category images"""
        stats = {"refreshed": 0, "errors": 0}
        
        try:
            # Use async database operations
            from app.utils.async_db_utils import get_async_session
            
            async with get_async_session() as session:
                result = await session.execute(select(Category))
                categories = result.scalars().all()
                
                for category in categories:
                    if category.box_art_url and category.box_art_url.startswith('http'):
                        # Check if cached file exists
                        safe_name = sanitize_filename(category.name)
                        expected_path = self.media_dir / "categories" / f"{safe_name}.jpg"
                        
                        if not expected_path.exists():
                            logger.info(f"Category image missing for {category.name}, re-downloading...")
                            try:
                                cached_path = await unified_image_service.download_category_image(
                                    category.name, 
                                    category.box_art_url
                                )
                                if cached_path:
                                    # Update database with cached path
                                    category.box_art_url = cached_path
                                    stats["refreshed"] += 1
                                    logger.info(f"Successfully refreshed category image for {category.name}")
                                else:
                                    stats["errors"] += 1
                            except Exception as e:
                                logger.error(f"Error refreshing category image for {category.name}: {e}")
                                stats["errors"] += 1
                
        except Exception as e:
            logger.error(f"Error refreshing category images: {e}")
            stats["errors"] += 1
            
        return stats
    
    async def _refresh_missing_stream_artwork(self) -> Dict[str, int]:
        """Check and refresh missing stream artwork"""
        stats = {"refreshed": 0, "errors": 0}
        
        try:
            # Use async database operations with batch processing
            from app.utils.async_db_utils import get_recent_streams, batch_process_items
            streams = await get_recent_streams(limit=100)
            
            # Process streams in batches for better performance
            async for batch in batch_process_items(streams, batch_size=5, max_concurrent=2):
                batch_tasks = []
                for stream in batch:
                    # Check if cached file exists
                    expected_path = self.media_dir / "artwork" / f"streamer_{stream.streamer_id}" / f"stream_{stream.id}.jpg"
                    
                    if not expected_path.exists() and stream.thumbnail_url:
                        logger.info(f"Stream artwork missing for stream {stream.id}, re-downloading...")
                        task = self._download_stream_artwork(stream)
                        batch_tasks.append(task)
                
                # Process batch concurrently
                if batch_tasks:
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.error(f"Error in batch stream artwork download: {result}")
                            stats["errors"] += 1
                        elif result:
                            stats["refreshed"] += 1
                
        except Exception as e:
            logger.error(f"Error refreshing stream artwork: {e}")
            stats["errors"] += 1
            
        return stats
    
    async def _download_stream_artwork(self, stream: Stream) -> bool:
        """Download stream artwork for a single stream"""
        try:
            cached_path = await unified_image_service.download_stream_artwork(
                stream.id, 
                stream.streamer_id,
                stream.thumbnail_url
            )
            if cached_path:
                logger.info(f"Successfully refreshed stream artwork for stream {stream.id}")
                return True
            else:
                logger.warning(f"Failed to download stream artwork for stream {stream.id}")
                return False
        except Exception as e:
            logger.error(f"Error refreshing stream artwork for stream {stream.id}: {e}")
            return False
    
    async def refresh_specific_streamer(self, streamer_id: int) -> bool:
        """Refresh images for a specific streamer"""
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    return False
                
                if streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
                    cached_path = await unified_image_service.download_profile_image(
                        streamer.id, 
                        streamer.profile_image_url
                    )
                    if cached_path:
                        streamer.profile_image_url = cached_path
                        logger.info(f"Refreshed profile image for streamer {streamer_id}")
                        return True
                        
        except Exception as e:
            logger.error(f"Error refreshing images for streamer {streamer_id}: {e}")
            
        return False
    
    async def refresh_specific_category(self, category_name: str) -> bool:
        """Refresh image for a specific category"""
        try:
            with SessionLocal() as db:
                category = db.query(Category).filter(Category.name == category_name).first()
                if not category:
                    return False
                
                if category.box_art_url and category.box_art_url.startswith('http'):
                    cached_path = await unified_image_service.download_category_image(
                        category.name, 
                        category.box_art_url
                    )
                    if cached_path:
                        category.box_art_url = cached_path
                        logger.info(f"Refreshed category image for {category_name}")
                        return True
                        
        except Exception as e:
            logger.error(f"Error refreshing image for category {category_name}: {e}")
            
        return False

# Global instance
image_refresh_service = ImageRefreshService()
