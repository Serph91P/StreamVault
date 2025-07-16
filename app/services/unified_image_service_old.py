"""
Unified Image Service for StreamVault

This service manages all images (profile pictures, category images, artwork) in a centralized way.
Images are stored in the recordings directory under a hidden .images folder so they are accessible
to media servers via the same volume mount.

Directory structure:
/recordings/.images/
├── profiles/          # Streamer profile images
│   ├── streamer_123.jpg
│   └── streamer_456.jpg
├── categories/        # Category/game images
│   ├── just_chatting.jpg
│   └── league_of_legends.jpg
└── artwork/          # Stream artwork/thumbnails
    ├── streamer_123/
    │   ├── stream_789.jpg
    │   └── stream_790.jpg
    └── streamer_456/
        └── stream_791.jpg
"""

import os
import asyncio
import aiohttp
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.database import SessionLocal
from app.models import Stream, Streamer, Category
from app.services.recording.config_manager import ConfigManager

try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

logger = logging.getLogger("streamvault")

class UnifiedImageService:
    """Unified service for managing all images in StreamVault"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.config_manager = ConfigManager()
        
        # Initialize basic properties
        self._initialized = False
        self.recordings_dir = None
        self.images_base_dir = None
        self.profiles_dir = None
        self.categories_dir = None
        self.artwork_dir = None
        
        # Caches for avoiding repeated downloads
        self._profile_cache: Dict[str, str] = {}
        self._category_cache: Dict[str, str] = {}
        self._failed_downloads: Set[str] = set()
    
    def _ensure_initialized(self):
        """Ensure the service is initialized (lazy initialization)"""
        if not self._initialized:
            try:
                # Get recordings directory from config
                self.recordings_dir = Path(self.config_manager.get_recordings_directory())
                
                # Create hidden .images directory in recordings
                self.images_base_dir = self.recordings_dir / ".images"
                self.profiles_dir = self.images_base_dir / "profiles"
                self.categories_dir = self.images_base_dir / "categories"
                self.artwork_dir = self.images_base_dir / "artwork"
                
                # Ensure directories exist
                self.images_base_dir.mkdir(parents=True, exist_ok=True)
                self.profiles_dir.mkdir(parents=True, exist_ok=True)
                self.categories_dir.mkdir(parents=True, exist_ok=True)
                self.artwork_dir.mkdir(parents=True, exist_ok=True)
                
                # Load existing cached images
                self._load_existing_cache()
                
                self._initialized = True
                logger.info(f"Unified image service initialized, storage: {self.images_base_dir}")
            except Exception as e:
                logger.error(f"Failed to initialize unified image service: {e}")
                # Fallback to a default directory if config fails
                self.recordings_dir = Path("/recordings")
                self.images_base_dir = self.recordings_dir / ".images"
                self.profiles_dir = self.images_base_dir / "profiles"
                self.categories_dir = self.images_base_dir / "categories"
                self.artwork_dir = self.images_base_dir / "artwork"
                
                # Ensure directories exist
                self.images_base_dir.mkdir(parents=True, exist_ok=True)
                self.profiles_dir.mkdir(parents=True, exist_ok=True)
                self.categories_dir.mkdir(parents=True, exist_ok=True)
                self.artwork_dir.mkdir(parents=True, exist_ok=True)
                
                self._initialized = True
                logger.warning(f"Unified image service initialized with fallback directory: {self.images_base_dir}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _load_existing_cache(self):
        """Load information about already cached images"""
        try:
            # Load profile images
            if self.profiles_dir and self.profiles_dir.exists():
                for image_file in self.profiles_dir.glob("*.jpg"):
                    streamer_id = image_file.stem.replace("streamer_", "")
                    self._profile_cache[streamer_id] = f"/data/images/profiles/{image_file.name}"
            
            # Load category images
            if self.categories_dir and self.categories_dir.exists():
                for image_file in self.categories_dir.glob("*.jpg"):
                    category_name = self._filename_to_category(image_file.stem)
                    if category_name:
                        self._category_cache[category_name] = f"/data/images/categories/{image_file.name}"
            
            logger.info(f"Loaded image cache: {len(self._profile_cache)} profiles, {len(self._category_cache)} categories")
        except Exception as e:
            logger.error(f"Error loading image cache: {e}")
    
    def _filename_to_category(self, filename: str) -> Optional[str]:
        """Convert filename back to category name"""
        # For now, assume filename is the category name with special chars replaced
        # This is a simplified approach - in production you might want a mapping file
        return filename.replace("_", " ").replace("-", " ")
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for filesystem"""
        import re
        # Replace special characters with underscores
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Replace spaces with underscores
        safe_name = safe_name.replace(' ', '_')
        # Remove multiple underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        return safe_name.strip('_').lower()
    
    def _create_filename_hash(self, url: str) -> str:
        """Create a hash-based filename for an image URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    # Profile Image Methods
    
    async def download_profile_image(self, streamer_id: int, profile_image_url: str) -> Optional[str]:
        """
        Download and cache a streamer's profile image
        
        Args:
            streamer_id: ID of the streamer
            profile_image_url: URL of the profile image
            
        Returns:
            Relative path to the cached image or None if failed
        """
        self._ensure_initialized()
        
        if not HAS_AIOFILES:
            logger.warning("aiofiles not available, cannot download profile image")
            return None
            
        if not profile_image_url:
            return None
            
        # Check if already cached
        streamer_id_str = str(streamer_id)
        if streamer_id_str in self._profile_cache:
            return self._profile_cache[streamer_id_str]
            
        # Skip if previously failed
        if profile_image_url in self._failed_downloads:
            return None
            
        try:
            filename = f"streamer_{streamer_id}.jpg"
            file_path = self.profiles_dir / filename
            
            session = await self._get_session()
            async with session.get(profile_image_url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type:
                        # Download and save
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        # Update cache
                        relative_path = f"/data/images/profiles/{filename}"
                        self._profile_cache[streamer_id_str] = relative_path
                        
                        # Update database with new image path
                        try:
                            with SessionLocal() as db:
                                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                                if streamer:
                                    streamer.profile_image_url = relative_path
                                    db.commit()
                                    logger.debug(f"Updated profile image path in database for streamer {streamer_id}")
                        except Exception as db_error:
                            logger.error(f"Failed to update profile image path in database: {db_error}")
                        
                        logger.info(f"Downloaded profile image for streamer {streamer_id}")
                        return relative_path
                    else:
                        logger.warning(f"Invalid content type for profile image: {content_type}")
                else:
                    logger.warning(f"Failed to download profile image, status: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error downloading profile image for streamer {streamer_id}: {e}")
            self._failed_downloads.add(profile_image_url)
            
        return None
    
    def get_profile_image_url(self, streamer_id: int, fallback_url: str = None) -> str:
        """
        Get the URL for a streamer's profile image (cached or fallback)
        
        Args:
            streamer_id: ID of the streamer
            fallback_url: Fallback URL if cached image not available
            
        Returns:
            URL to the profile image
        """
        self._ensure_initialized()
        streamer_id_str = str(streamer_id)
        
        # Check cache first
        if streamer_id_str in self._profile_cache:
            return self._profile_cache[streamer_id_str]
            
        # Check if we have a fallback URL that's already a local path
        if fallback_url and fallback_url.startswith('/data/images/'):
            return fallback_url
            
        # Check if fallback is original Twitch URL - try to download it
        if fallback_url and fallback_url.startswith('https://'):
            # Try to download the profile image in the background
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task to download the image
                    asyncio.create_task(self.download_profile_image(streamer_id, fallback_url))
            except Exception as e:
                logger.debug(f"Could not create background download task: {e}")
            
            # Return original URL for now, but will be cached next time
            return fallback_url
            
        # Default Twitch profile image
        return "https://static-cdn.jtvnw.net/user-default-pictures-uv/de130ab0-def7-11e9-b668-784f43822e80-profile_image-70x70.png"
    
    # Category Image Methods
    
    async def download_category_image(self, category_name: str, image_url: str = None) -> Optional[str]:
        """
        Download and cache a category/game image
        
        Args:
            category_name: Name of the category
            image_url: URL of the category image (if None, will try to get from Twitch)
            
        Returns:
            Relative path to the cached image or None if failed
        """
        self._ensure_initialized()
        if not HAS_AIOFILES:
            logger.warning("aiofiles not available, cannot download category image")
            return None
            
        if not category_name:
            return None
            
        # Check if already cached
        if category_name in self._category_cache:
            return self._category_cache[category_name]
            
        # Skip if previously failed
        cache_key = f"category_{category_name}"
        if cache_key in self._failed_downloads:
            return None
            
        try:
            # If no URL provided, try to get from Twitch API
            if not image_url:
                image_url = await self._get_twitch_category_image_url(category_name)
                
            if not image_url:
                return None
                
            filename = f"{self._sanitize_filename(category_name)}.jpg"
            file_path = self.categories_dir / filename
            
            session = await self._get_session()
            async with session.get(image_url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type:
                        # Download and save
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        # Update cache
                        relative_path = f"/data/images/categories/{filename}"
                        self._category_cache[category_name] = relative_path
                        
                        logger.info(f"Downloaded category image for: {category_name}")
                        return relative_path
                    else:
                        logger.warning(f"Invalid content type for category image: {content_type}")
                else:
                    logger.warning(f"Failed to download category image, status: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error downloading category image for {category_name}: {e}")
            self._failed_downloads.add(cache_key)
            
        return None
    
    async def _get_twitch_category_image_url(self, category_name: str) -> Optional[str]:
        """
        Get Twitch category image URL from Twitch API
        
        This uses the actual Twitch API to get the correct box art URL
        """
        try:
            # Import twitch_api dynamically to avoid circular imports
            try:
                from app.services.twitch_api import twitch_api
            except Exception as e:
                logger.debug(f"Could not import twitch_api service: {e}")
                return None
            
            # Search for the game/category
            games = await twitch_api.get_games_by_name([category_name])
            if games and len(games) > 0:
                game = games[0]
                # Get the box art URL and replace template with actual size
                box_art_url = game.get('box_art_url', '')
                if box_art_url:
                    # Replace template with actual size
                    return box_art_url.replace('{width}', '285').replace('{height}', '380')
            
            # Fallback: try some common category mappings
            category_mappings = {
                'Just Chatting': 'https://static-cdn.jtvnw.net/ttv-boxart/509658-285x380.jpg',
                'League of Legends': 'https://static-cdn.jtvnw.net/ttv-boxart/21779-285x380.jpg',
                'Fortnite': 'https://static-cdn.jtvnw.net/ttv-boxart/33214-285x380.jpg',
                'Minecraft': 'https://static-cdn.jtvnw.net/ttv-boxart/27471-285x380.jpg',
                'Grand Theft Auto V': 'https://static-cdn.jtvnw.net/ttv-boxart/32982-285x380.jpg',
                'Valorant': 'https://static-cdn.jtvnw.net/ttv-boxart/516575-285x380.jpg',
                'Counter-Strike 2': 'https://static-cdn.jtvnw.net/ttv-boxart/32399-285x380.jpg',
                'World of Warcraft': 'https://static-cdn.jtvnw.net/ttv-boxart/18122-285x380.jpg',
                'Dota 2': 'https://static-cdn.jtvnw.net/ttv-boxart/29595-285x380.jpg',
                'Apex Legends': 'https://static-cdn.jtvnw.net/ttv-boxart/511224-285x380.jpg'
            }
            
            if category_name in category_mappings:
                return category_mappings[category_name]
                
            return None
            
        except Exception as e:
            logger.debug(f"Could not get Twitch category image for {category_name}: {e}")
            return None
    
    def get_category_image_url(self, category_name: str, fallback_url: str = None) -> str:
        """
        Get the URL for a category image (cached or fallback)
        
        Args:
            category_name: Name of the category
            fallback_url: Fallback URL if cached image not available
            
        Returns:
            URL to the category image
        """
        self._ensure_initialized()
        # Check cache first
        if category_name in self._category_cache:
            return self._category_cache[category_name]
            
        # Check if we have a fallback URL that's already a local path
        if fallback_url and fallback_url.startswith('/data/images/'):
            return fallback_url
            
        # Check if fallback is a Twitch URL - try to download it
        if fallback_url and fallback_url.startswith('https://'):
            # Try to download the category image in the background
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task to download the image
                    asyncio.create_task(self.download_category_image(category_name))
            except Exception as e:
                logger.debug(f"Could not create background download task: {e}")
            
            # Return icon fallback for now (Frontend will handle this)
            return f"icon:fa-gamepad"
            
        # Default category image - return icon fallback
        return f"icon:fa-gamepad"
    
    # Stream Artwork Methods
    
    async def download_stream_artwork(self, stream_id: int, streamer_id: int, artwork_url: str) -> Optional[str]:
        """
        Download and cache stream artwork/thumbnail
        
        Args:
            stream_id: ID of the stream
            streamer_id: ID of the streamer
            artwork_url: URL of the artwork
            
        Returns:
            Relative path to the cached artwork or None if failed
        """
        if not HAS_AIOFILES:
            logger.warning("aiofiles not available, cannot download stream artwork")
            return None
            
        if not artwork_url:
            return None
            
        try:
            # Create streamer artwork directory
            streamer_artwork_dir = self.artwork_dir / f"streamer_{streamer_id}"
            streamer_artwork_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"stream_{stream_id}.jpg"
            file_path = streamer_artwork_dir / filename
            
            # Skip if already exists
            if file_path.exists():
                return f"/data/images/artwork/streamer_{streamer_id}/{filename}"
                
            session = await self._get_session()
            async with session.get(artwork_url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type:
                        # Download and save
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        relative_path = f"/data/images/artwork/streamer_{streamer_id}/{filename}"
                        logger.info(f"Downloaded stream artwork for stream {stream_id}")
                        return relative_path
                    else:
                        logger.warning(f"Invalid content type for stream artwork: {content_type}")
                else:
                    logger.warning(f"Failed to download stream artwork, status: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error downloading stream artwork for stream {stream_id}: {e}")
            
        return None
    
    # Bulk Operations
    
    async def sync_all_profile_images(self):
        """Download/update all streamer profile images"""
        try:
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                
            tasks = []
            for streamer in streamers:
                if streamer.profile_image_url:
                    task = self.download_profile_image(streamer.id, streamer.profile_image_url)
                    tasks.append(task)
                    
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is not None and not isinstance(r, Exception))
                logger.info(f"Synced {success_count}/{len(tasks)} profile images")
                
        except Exception as e:
            logger.error(f"Error syncing profile images: {e}")
    
    async def sync_all_category_images(self):
        """Download/update all category images"""
        try:
            with SessionLocal() as db:
                categories = db.query(Category).all()
                
            tasks = []
            for category in categories:
                if category.name:
                    task = self.download_category_image(category.name)
                    tasks.append(task)
                    
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is not None and not isinstance(r, Exception))
                logger.info(f"Synced {success_count}/{len(tasks)} category images")
                
        except Exception as e:
            logger.error(f"Error syncing category images: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about cached images"""
        self._ensure_initialized()
        return {
            "profiles_cached": len(self._profile_cache),
            "categories_cached": len(self._category_cache),
            "failed_downloads": len(self._failed_downloads),
            "storage_path": str(self.images_base_dir),
            "profiles_dir_size": self._get_directory_size(self.profiles_dir),
            "categories_dir_size": self._get_directory_size(self.categories_dir),
            "artwork_dir_size": self._get_directory_size(self.artwork_dir)
        }
    
    def get_missing_images_report(self) -> Dict[str, Any]:
        """Get a report of categories that are missing images"""
        self._ensure_initialized()
        try:
            with SessionLocal() as db:
                all_categories = db.query(Category).all()
                
                missing_images = []
                have_images = []
                
                for category in all_categories:
                    if category.name in self._category_cache:
                        # Check if the file actually exists
                        cache_path = self._category_cache[category.name]
                        filename = cache_path.split('/')[-1]  # Get filename from path
                        file_path = self.categories_dir / filename
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
    
    async def preload_categories(self, category_names: List[str]) -> Dict[str, Any]:
        """Preload category images for the given category names"""
        self._ensure_initialized()
        try:
            results = []
            for category_name in category_names:
                try:
                    # Download category image
                    image_path = await self.download_category_image(category_name)
                    if image_path:
                        results.append({
                            "category": category_name,
                            "status": "success",
                            "image_path": image_path
                        })
                    else:
                        results.append({
                            "category": category_name,
                            "status": "failed",
                            "error": "Failed to download image"
                        })
                except Exception as e:
                    results.append({
                        "category": category_name,
                        "status": "failed",
                        "error": str(e)
                    })
            
            success_count = sum(1 for r in results if r["status"] == "success")
            
            return {
                "message": f"Preloaded {success_count}/{len(category_names)} category images",
                "results": results,
                "success_count": success_count,
                "total_count": len(category_names)
            }
        except Exception as e:
            logger.error(f"Error preloading categories: {e}")
            return {
                "error": "Failed to preload categories",
                "message": str(e)
            }
    
    def cleanup_old_images(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old cached images that haven't been accessed in the specified number of days"""
        self._ensure_initialized()
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cleaned_files = []
            
            # Clean up old category images
            if self.categories_dir.exists():
                for image_file in self.categories_dir.glob("*.jpg"):
                    try:
                        # Check file modification time
                        file_stat = image_file.stat()
                        file_date = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        if file_date < cutoff_date:
                            # Remove from cache
                            category_name = self._filename_to_category(image_file.stem)
                            if category_name and category_name in self._category_cache:
                                del self._category_cache[category_name]
                            
                            # Delete file
                            image_file.unlink()
                            cleaned_files.append(str(image_file))
                            logger.info(f"Cleaned up old category image: {image_file.name}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {image_file}: {e}")
            
            # Clean up old profile images
            if self.profiles_dir.exists():
                for image_file in self.profiles_dir.glob("*.jpg"):
                    try:
                        # Check file modification time
                        file_stat = image_file.stat()
                        file_date = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        if file_date < cutoff_date:
                            # Remove from cache
                            streamer_id = image_file.stem.replace("streamer_", "")
                            if streamer_id in self._profile_cache:
                                del self._profile_cache[streamer_id]
                            
                            # Delete file
                            image_file.unlink()
                            cleaned_files.append(str(image_file))
                            logger.info(f"Cleaned up old profile image: {image_file.name}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {image_file}: {e}")
            
            return {
                "message": f"Cleaned up {len(cleaned_files)} old images",
                "cleaned_files": cleaned_files,
                "cleanup_count": len(cleaned_files)
            }
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                "error": "Failed to cleanup old images",
                "message": str(e)
            }
    
    def _get_directory_size(self, path: Path) -> int:
        """Get total size of directory in bytes"""
        try:
            total_size = 0
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception:
            return 0
    
    # Cleanup Methods
    
    def cleanup_orphaned_images(self):
        """Remove images that are no longer referenced"""
        try:
            with SessionLocal() as db:
                # Get all active streamer IDs
                active_streamer_ids = set(str(s.id) for s in db.query(Streamer.id).all())
                
                # Clean up orphaned profile images
                for image_file in self.profiles_dir.glob("*.jpg"):
                    streamer_id = image_file.stem.replace("streamer_", "")
                    if streamer_id not in active_streamer_ids:
                        image_file.unlink()
                        logger.info(f"Removed orphaned profile image: {image_file}")
                        
                # Get all active category names
                active_categories = set(c.name for c in db.query(Category.name).all())
                
                # Clean up orphaned category images
                for image_file in self.categories_dir.glob("*.jpg"):
                    category_name = self._filename_to_category(image_file.stem)
                    if category_name not in active_categories:
                        image_file.unlink()
                        logger.info(f"Removed orphaned category image: {image_file}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up orphaned images: {e}")

# Global instance
unified_image_service = UnifiedImageService()
