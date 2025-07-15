"""
Service for managing category images - downloading and caching Twitch category box art
"""
import os
import asyncio
import aiohttp
from typing import Optional, Dict, Set

try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False
from urllib.parse import quote
import hashlib
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Category

logger = logging.getLogger(__name__)

class CategoryImageService:
    def __init__(self, images_dir: str = "/app/data/category_images"):
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for known categories to avoid repeated checks
        self._category_cache: Dict[str, str] = {}
        self._failed_downloads: Set[str] = set()
        
        # Load existing cached categories
        self._load_existing_cache()
    
    def _load_existing_cache(self):
        """Load information about already cached images"""
        if self.images_dir.exists():
            for image_file in self.images_dir.glob("*.jpg"):
                # Extract category name from filename - this is tricky with the hash system
                category_name = self._filename_to_category(image_file.stem)
                if category_name:
                    # Use /data path for web access
                    self._category_cache[category_name] = f"/data/category_images/{image_file.name}"
            
            # Also check if we have any categories in database that match our cache
            try:
                db = SessionLocal()
                try:
                    db_categories = db.query(Category).all()
                    for category in db_categories:
                        if category.name not in self._category_cache:
                            # Check if we have an image file for this category
                            filename = self._category_to_filename(category.name)
                            file_path = self.images_dir / f"{filename}.jpg"
                            if file_path.exists():
                                self._category_cache[category.name] = f"/data/category_images/{filename}.jpg"
                                logger.debug(f"Found cached image for {category.name}")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Could not load database categories for cache: {e}")
        
        logger.info(f"Loaded {len(self._category_cache)} cached category images")
    
    def _category_to_filename(self, category_name: str) -> str:
        """Convert category name to safe filename"""
        # Create a safe filename using hash to avoid issues with special characters
        safe_name = "".join(c for c in category_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_').lower()
        
        # Add hash to ensure uniqueness and handle edge cases
        category_hash = hashlib.md5(category_name.encode()).hexdigest()[:8]
        return f"{safe_name}_{category_hash}"
    
    def _filename_to_category(self, filename: str) -> Optional[str]:
        """Try to extract category name from filename (for cache loading)"""
        # This is a reverse lookup - not perfect but helps with cache loading
        # Try to match with database categories by filename patterns
        try:
            db = SessionLocal()
            try:
                all_categories = db.query(Category).all()
                for category in all_categories:
                    expected_filename = self._category_to_filename(category.name)
                    if expected_filename == filename:
                        return category.name
                
                # Fallback: try to parse from filename structure
                parts = filename.split('_')
                if len(parts) >= 2:
                    # Remove the hash part and reconstruct
                    category_parts = parts[:-1]  # Remove hash
                    return ' '.join(part.replace('_', ' ').title() for part in category_parts)
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Could not lookup category name for filename {filename}: {e}")
        
        return None
    
    def get_category_image_url(self, category_name: str) -> str:
        """Get the URL for a category image (local if cached, fallback to default)"""
        if not category_name:
            return "/data/category_images/default-category.svg"
        
        # Check if we have it cached
        if category_name in self._category_cache:
            return self._category_cache[category_name]
        
        # Check if we already failed to download this
        if category_name in self._failed_downloads:
            return self._get_fallback_image(category_name)
        
        # Trigger async download (don't wait for it)
        asyncio.create_task(self._download_category_image(category_name))
        
        # Return fallback for now
        return self._get_fallback_image(category_name)
    
    def _get_fallback_image(self, category_name: str) -> str:
        """Get a fallback image URL/icon class"""
        # Map to FontAwesome icons as fallback
        category_icons = {
            'Just Chatting': 'fa-comments',
            'League of Legends': 'fa-gamepad',
            'Valorant': 'fa-crosshairs',
            'Minecraft': 'fa-cube',
            'Grand Theft Auto V': 'fa-car',
            'Counter-Strike 2': 'fa-bullseye',
            'World of Warcraft': 'fa-magic',
            'Fortnite': 'fa-gamepad',
            'Apex Legends': 'fa-trophy',
            'Call of Duty': 'fa-bomb',
            'Music': 'fa-music',
            'Art': 'fa-palette',
            'Science & Technology': 'fa-microscope',
            'Sports': 'fa-football-ball',
            'Travel & Outdoors': 'fa-mountain',
        }
        
        return f"icon:{category_icons.get(category_name, 'fa-gamepad')}"
    
    async def _download_category_image(self, category_name: str) -> bool:
        """Download category image from Twitch CDN"""
        try:
            # First try to get the box art URL from database
            db = SessionLocal()
            try:
                category = db.query(Category).filter(Category.name == category_name).first()
                box_art_url = category.box_art_url if category else None
            finally:
                db.close()
            
            # Prepare URLs to try
            urls_to_try = []
            
            # If we have a box art URL from database, use it first
            if box_art_url:
                # Replace template size with our desired size
                actual_url = box_art_url.replace('{width}', '144').replace('{height}', '192')
                urls_to_try.append(actual_url)
                logger.debug(f"Using database box art URL for {category_name}: {actual_url}")
            
            # Fallback URLs based on category name (old method)
            urls_to_try.extend([
                f"https://static-cdn.jtvnw.net/ttv-boxart/{quote(category_name)}-144x192.jpg",
                f"https://static-cdn.jtvnw.net/ttv-boxart/{quote(category_name, safe='')}-144x192.jpg",
                f"https://static-cdn.jtvnw.net/ttv-boxart/{category_name.replace(' ', '%20')}-144x192.jpg",
            ])
            
            filename = self._category_to_filename(category_name)
            file_path = self.images_dir / f"{filename}.jpg"
            
            async with aiohttp.ClientSession() as session:
                for url in urls_to_try:
                    try:
                        logger.debug(f"Trying to download {category_name} from: {url}")
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                # Check if it's actually an image
                                content_type = response.headers.get('content-type', '')
                                if 'image' in content_type:
                                    if not HAS_AIOFILES:
                                        logger.warning("aiofiles not available, cannot download category image")
                                        return False
                                    
                                    # Download and save
                                    async with aiofiles.open(file_path, 'wb') as f:
                                        async for chunk in response.content.iter_chunked(8192):
                                            await f.write(chunk)
                                    
                                    # Update cache
                                    relative_path = f"/data/category_images/{filename}.jpg"
                                    self._category_cache[category_name] = relative_path
                                    
                                    logger.info(f"Successfully downloaded image for category: {category_name} from {url}")
                                    return True
                            else:
                                logger.debug(f"HTTP {response.status} for {url}")
                    except Exception as e:
                        logger.debug(f"Failed to download from {url}: {e}")
                        continue
            
            # If we get here, all downloads failed
            self._failed_downloads.add(category_name)
            logger.warning(f"Failed to download image for category: {category_name} from all URLs")
            return False
            
        except Exception as e:
            logger.error(f"Error downloading category image for {category_name}: {e}")
            self._failed_downloads.add(category_name)
            return False
    
    async def preload_categories(self, category_names: list[str]):
        """Preload multiple category images"""
        tasks = []
        for category_name in category_names:
            if category_name and category_name not in self._category_cache and category_name not in self._failed_downloads:
                tasks.append(self._download_category_image(category_name))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_downloads = sum(1 for result in results if result is True)
            logger.info(f"Preloaded {successful_downloads}/{len(tasks)} category images")
    
    async def refresh_category_images(self, category_names: list[str]):
        """Re-download category images even if they exist (for fixing missing/broken images)"""
        tasks = []
        for category_name in category_names:
            if category_name:
                # Remove from failed downloads to retry
                self._failed_downloads.discard(category_name)
                # Remove from cache to force re-download
                self._category_cache.pop(category_name, None)
                # Delete existing file if it exists
                filename = self._category_to_filename(category_name)
                file_path = self.images_dir / f"{filename}.jpg"
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.info(f"Deleted existing image for re-download: {category_name}")
                    except Exception as e:
                        logger.warning(f"Could not delete existing image {file_path}: {e}")
                
                tasks.append(self._download_category_image(category_name))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_downloads = sum(1 for result in results if result is True)
            logger.info(f"Refreshed {successful_downloads}/{len(tasks)} category images")
            return successful_downloads
        return 0
    
    def cleanup_old_images(self, days_old: int = 30):
        """Clean up old cached images that haven't been accessed recently"""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (days_old * 24 * 60 * 60)
            
            for image_file in self.images_dir.glob("*.jpg"):
                if image_file.stat().st_atime < cutoff_time:
                    try:
                        image_file.unlink()
                        # Remove from cache
                        category_name = self._filename_to_category(image_file.stem)
                        if category_name and category_name in self._category_cache:
                            del self._category_cache[category_name]
                        logger.info(f"Cleaned up old category image: {image_file.name}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {image_file}: {e}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_missing_images_report(self):
        """Get a report of categories that are missing images"""
        try:
            db = SessionLocal()
            try:
                all_categories = db.query(Category).all()
                
                missing_images = []
                have_images = []
                
                for category in all_categories:
                    if category.name in self._category_cache:
                        # Check if the file actually exists
                        cache_path = self._category_cache[category.name]
                        filename = cache_path.split('/')[-1]  # Get filename from path
                        file_path = self.images_dir / filename
                        if file_path.exists():
                            have_images.append(category.name)
                        else:
                            # Image in cache but file missing - remove from cache
                            del self._category_cache[category.name]
                            missing_images.append(category.name)
                    else:
                        missing_images.append(category.name)
                
                return {
                    "total_categories": len(all_categories),
                    "have_images": len(have_images),
                    "missing_images": len(missing_images),
                    "categories_with_images": have_images,
                    "categories_missing_images": missing_images
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error generating missing images report: {e}")
            return {
                "error": "An internal error occurred while generating the report.",
                "total_categories": 0,
                "have_images": 0,
                "missing_images": 0,
                "categories_with_images": [],
                "categories_missing_images": []
            }

# Global instance
category_image_service = CategoryImageService()
