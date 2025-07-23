"""
CategoryImageService - Category/game image management

Extracted from unified_image_service.py God Class
Handles downloading, caching, and serving of category/game images.
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Category
from .image_download_service import ImageDownloadService

logger = logging.getLogger("streamvault")


class CategoryImageService:
    """Handles category/game image management"""
    
    # Constants
    DEFAULT_CATEGORY_IMAGE_PATH = "/api/media/categories/default-category.svg"
    
    def __init__(self, download_service: Optional[ImageDownloadService] = None):
        self.download_service = download_service or ImageDownloadService()
        self._category_cache: Dict[str, str] = {}
        self.categories_dir = None
        self._load_existing_cache()
    
    def _ensure_categories_dir(self):
        """Ensure categories directory exists"""
        if self.categories_dir is None:
            try:
                images_base_dir = self.download_service.get_images_base_dir()
                self.categories_dir = images_base_dir / "categories"
                self.categories_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to initialize categories directory: {e}")
                # Fallback to a temporary path
                self.categories_dir = Path(tempfile.gettempdir()) / "categories"
                self.categories_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_existing_cache(self):
        """Load information about already cached category images"""
        try:
            self._ensure_categories_dir()
            
            if self.categories_dir is not None and self.categories_dir.exists():
                for image_file in self.categories_dir.glob("*.jpg"):
                    category_name = self._filename_to_category(image_file.stem)
                    if category_name:
                        self._category_cache[category_name] = f"/api/media/categories/{image_file.name}"
            
            logger.info(f"Loaded category image cache: {len(self._category_cache)} categories")
        except Exception as e:
            logger.error(f"Error loading category image cache: {e}")
            # Initialize empty cache if loading fails
            self._category_cache = {}

    def _filename_to_category(self, filename: str) -> Optional[str]:
        """Convert filename back to category name"""
        # For now, assume filename is the category name with special chars replaced
        # This is a simplified approach - in production you might want a mapping file
        return filename.replace("_", " ").replace("-", " ")

    async def download_category_image(self, category_name: str, box_art_url: str) -> Optional[str]:
        """
        Download and cache a category's box art image
        
        Args:
            category_name: Name of the category/game
            box_art_url: URL of the box art image
            
        Returns:
            Relative path to the cached image or None if failed
        """
        self._ensure_categories_dir()
            
        if not box_art_url or not category_name:
            return None
            
        # Check if already cached
        if category_name in self._category_cache:
            return self._category_cache[category_name]
            
        # Skip if previously failed
        if self.download_service.is_download_failed(box_art_url):
            return None
            
        try:
            self._ensure_categories_dir()
            if self.categories_dir is None:
                logger.error("Categories directory not initialized")
                return None
                
            safe_name = self.download_service.sanitize_filename(category_name)
            filename = f"{safe_name}.jpg"
            file_path = self.categories_dir / filename
            
            success = await self.download_service.download_image(box_art_url, file_path)
            if success:
                relative_path = f"/api/media/categories/{filename}"
                self._category_cache[category_name] = relative_path
                logger.info(f"Successfully cached category image for {category_name}")
                return relative_path
            else:
                logger.warning(f"Failed to download category image for {category_name}")
                self.download_service.mark_download_failed(box_art_url)
                return None
                
        except Exception as e:
            logger.error(f"Error downloading category image for {category_name}: {e}")
            self.download_service.mark_download_failed(box_art_url)
            return None

    def get_cached_category_image(self, category_name: str) -> Optional[str]:
        """Get cached category image path with fast fallback"""
        # First check the memory cache (fastest)
        cached_path = self._category_cache.get(category_name)
        if cached_path:
            return cached_path
        
        # Return default image to avoid blocking on database
        return self.DEFAULT_CATEGORY_IMAGE_PATH

    async def update_category_image(self, category_name: str, box_art_url: str) -> bool:
        """Update a category's image in database and cache"""
        try:
            # Download the image
            cached_path = await self.download_category_image(category_name, box_art_url)
            
            if cached_path:
                # Update database
                with SessionLocal() as db:
                    category = db.query(Category).filter(Category.name == category_name).first()
                    if category:
                        category.box_art_url = cached_path
                        db.commit()
                        logger.info(f"Updated category image for {category_name}")
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"Error updating category image for {category_name}: {e}")
            return False

    async def sync_all_category_images(self) -> Dict[str, int]:
        """Sync all category images for all categories"""
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        
        try:
            with SessionLocal() as db:
                categories = db.query(Category).all()
                
                for category in categories:
                    if category.box_art_url and category.box_art_url.startswith('http'):
                        # This is a Twitch URL, download and cache it
                        cached_path = await self.download_category_image(category.name, category.box_art_url)
                        if cached_path:
                            # Update to use cached path
                            category.box_art_url = cached_path
                            stats["downloaded"] += 1
                        else:
                            stats["failed"] += 1
                    else:
                        stats["skipped"] += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error syncing category images: {e}")
            
        logger.info(f"Category image sync completed: {stats}")
        return stats

    async def bulk_sync_categories(self, category_data: List[Dict]) -> Dict[str, int]:
        """Bulk sync category images from Twitch API data"""
        stats = {"updated": 0, "downloaded": 0, "failed": 0}
        
        try:
            with SessionLocal() as db:
                for cat_info in category_data:
                    category_name = cat_info.get('name')
                    box_art_url = cat_info.get('box_art_url')
                    
                    if not category_name or not box_art_url:
                        continue
                    
                    # Check if category exists
                    category = db.query(Category).filter(Category.name == category_name).first()
                    if not category:
                        # Create new category
                        category = Category(
                            name=category_name,
                            twitch_id=cat_info.get('id'),
                            box_art_url=box_art_url
                        )
                        db.add(category)
                        stats["updated"] += 1
                    
                    # Download image if it's a HTTP URL
                    if box_art_url.startswith('http'):
                        cached_path = await self.download_category_image(category_name, box_art_url)
                        if cached_path:
                            category.box_art_url = cached_path
                            stats["downloaded"] += 1
                        else:
                            stats["failed"] += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error during bulk category sync: {e}")
            
        logger.info(f"Bulk category sync completed: {stats}")
        return stats

    def get_category_cache_stats(self) -> Dict[str, int]:
        """Get statistics about category image cache"""
        return {
            "cached_categories": len(self._category_cache),
            "failed_downloads": len([url for url in self.download_service._failed_downloads if 'category' in url or 'box_art' in url])
        }

    async def cleanup_unused_category_images(self) -> int:
        """Remove category images that are no longer associated with any category"""
        cleaned_count = 0
        
        try:
            self._ensure_categories_dir()
            
            # Get all category names from database
            with SessionLocal() as db:
                active_categories = set(c.name for c in db.query(Category.name).all())
            
            # Check cached images
            for image_file in self.categories_dir.glob("*.jpg"):
                category_name = self._filename_to_category(image_file.stem)
                
                if category_name and category_name not in active_categories:
                    try:
                        image_file.unlink()
                        # Remove from cache
                        self._category_cache.pop(category_name, None)
                        cleaned_count += 1
                        logger.info(f"Removed unused category image: {image_file.name}")
                    except Exception as e:
                        logger.error(f"Error removing category image {image_file}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during category image cleanup: {e}")
            
        return cleaned_count

    async def close(self):
        """Close the download service"""
        await self.download_service.close()
