"""
Image Refresh Service

Handles automatic re-downloading of missing images and frontend integration.
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Streamer, Category, Stream
from app.services.images.unified_image_service import unified_image_service

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
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                
                for streamer in streamers:
                    if streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
                        # Check if cached file exists
                        expected_path = self.media_dir / "profiles" / f"streamer_{streamer.id}.jpg"
                        
                        if not expected_path.exists():
                            logger.info(f"Profile image missing for streamer {streamer.id}, re-downloading...")
                            try:
                                cached_path = await unified_image_service.download_profile_image(
                                    streamer.id, 
                                    streamer.profile_image_url
                                )
                                if cached_path:
                                    # Update database with cached path
                                    streamer.profile_image_url = cached_path
                                    stats["refreshed"] += 1
                                    logger.info(f"Successfully refreshed profile image for streamer {streamer.id}")
                                else:
                                    stats["errors"] += 1
                            except Exception as e:
                                logger.error(f"Error refreshing profile image for streamer {streamer.id}: {e}")
                                stats["errors"] += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error refreshing profile images: {e}")
            stats["errors"] += 1
            
        return stats
    
    async def _refresh_missing_category_images(self) -> Dict[str, int]:
        """Check and refresh missing category images"""
        stats = {"refreshed": 0, "errors": 0}
        
        try:
            with SessionLocal() as db:
                categories = db.query(Category).all()
                
                for category in categories:
                    if category.box_art_url and category.box_art_url.startswith('http'):
                        # Check if cached file exists
                        safe_name = unified_image_service.download_service.sanitize_filename(category.name)
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
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error refreshing category images: {e}")
            stats["errors"] += 1
            
        return stats
    
    async def _refresh_missing_stream_artwork(self) -> Dict[str, int]:
        """Check and refresh missing stream artwork"""
        stats = {"refreshed": 0, "errors": 0}
        
        try:
            with SessionLocal() as db:
                # Only check recent streams to avoid overloading
                from sqlalchemy import desc
                streams = db.query(Stream).filter(
                    Stream.thumbnail_url.isnot(None),
                    Stream.thumbnail_url.like('http%')
                ).order_by(desc(Stream.started_at)).limit(100).all()
                
                for stream in streams:
                    # Check if cached file exists
                    expected_path = self.media_dir / "artwork" / f"streamer_{stream.streamer_id}" / f"stream_{stream.id}.jpg"
                    
                    if not expected_path.exists() and stream.thumbnail_url:
                        logger.info(f"Stream artwork missing for stream {stream.id}, re-downloading...")
                        try:
                            cached_path = await unified_image_service.download_stream_artwork(
                                stream.id, 
                                stream.streamer_id,
                                stream.thumbnail_url
                            )
                            if cached_path:
                                stats["refreshed"] += 1
                                logger.info(f"Successfully refreshed stream artwork for stream {stream.id}")
                            else:
                                stats["errors"] += 1
                        except Exception as e:
                            logger.error(f"Error refreshing stream artwork for stream {stream.id}: {e}")
                            stats["errors"] += 1
                
        except Exception as e:
            logger.error(f"Error refreshing stream artwork: {e}")
            stats["errors"] += 1
            
        return stats
    
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
                        db.commit()
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
                        db.commit()
                        logger.info(f"Refreshed category image for {category_name}")
                        return True
                        
        except Exception as e:
            logger.error(f"Error refreshing image for category {category_name}: {e}")
            
        return False

# Global instance
image_refresh_service = ImageRefreshService()
