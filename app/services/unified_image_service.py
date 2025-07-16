"""
UnifiedImageService - Backward compatibility wrapper

This is a lightweight wrapper around the refactored image services
to maintain backward compatibility while the codebase migrates to the new structure.

Original God Class (728 lines) split into:
- ImageDownloadService: HTTP download operations and session management
- ProfileImageService: Streamer profile image management
- CategoryImageService: Category/game image management  
- StreamArtworkService: Stream artwork/thumbnail management
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from app.services.images import (
    ImageDownloadService,
    ProfileImageService,
    CategoryImageService,
    StreamArtworkService
)

logger = logging.getLogger("streamvault")


class UnifiedImageService:
    """Backward compatibility wrapper for the refactored image services"""
    
    def __init__(self):
        # Initialize the refactored services
        self.download_service = ImageDownloadService()
        self.profile_service = ProfileImageService(self.download_service)
        self.category_service = CategoryImageService(self.download_service)
        self.artwork_service = StreamArtworkService(self.download_service)
        
        # Legacy properties for compatibility
        self.session = self.download_service.session
        self._initialized = True
        self.recordings_dir = None
        self.images_base_dir = None
        self.profiles_dir = None
        self.categories_dir = None
        self.artwork_dir = None
        self._profile_cache = self.profile_service._profile_cache
        self._category_cache = self.category_service._category_cache
        self._failed_downloads = self.download_service._failed_downloads
        
        # Initialize directories for legacy compatibility
        self._setup_legacy_properties()

    def _setup_legacy_properties(self):
        """Setup legacy properties for backward compatibility"""
        try:
            self.images_base_dir = self.download_service.get_images_base_dir()
            self.profiles_dir = self.images_base_dir / "profiles"
            self.categories_dir = self.images_base_dir / "categories"
            self.artwork_dir = self.images_base_dir / "artwork"
            self.recordings_dir = self.images_base_dir.parent
        except Exception as e:
            logger.error(f"Error setting up legacy properties: {e}")

    def _ensure_initialized(self):
        """Legacy method - already initialized"""
        pass

    async def _get_session(self):
        """Legacy method - get HTTP session"""
        return await self.download_service.get_session()

    async def close(self):
        """Close all services"""
        await self.download_service.close()

    def _load_existing_cache(self):
        """Legacy method - already loaded"""
        pass

    def _filename_to_category(self, filename: str) -> Optional[str]:
        """Legacy method"""
        return self.category_service._filename_to_category(filename)

    def _sanitize_filename(self, name: str) -> str:
        """Legacy method"""
        return self.download_service.sanitize_filename(name)

    def _create_filename_hash(self, url: str) -> str:
        """Legacy method"""
        return self.download_service.create_filename_hash(url)

    # Profile Image Methods (delegate to ProfileImageService)
    
    async def download_profile_image(self, streamer_id: int, profile_image_url: str) -> Optional[str]:
        """Download and cache a streamer's profile image"""
        return await self.profile_service.download_profile_image(streamer_id, profile_image_url)

    def get_cached_profile_image(self, streamer_id: int) -> Optional[str]:
        """Get cached profile image path"""
        return self.profile_service.get_cached_profile_image(streamer_id)

    def get_profile_image_url(self, streamer_id: int, original_url: str = None) -> Optional[str]:
        """Get profile image URL for a streamer (legacy compatibility method)"""
        # First try to get cached image
        cached_url = self.profile_service.get_cached_profile_image(streamer_id)
        if cached_url:
            return cached_url
        
        # If no cached image and original_url provided, return original
        return original_url

    async def update_streamer_profile_image(self, streamer_id: int, profile_image_url: str) -> bool:
        """Update a streamer's profile image"""
        return await self.profile_service.update_streamer_profile_image(streamer_id, profile_image_url)

    async def sync_all_profile_images(self) -> Dict[str, int]:
        """Sync all profile images"""
        return await self.profile_service.sync_all_profile_images()

    # Category Image Methods (delegate to CategoryImageService)
    
    async def download_category_image(self, category_name: str, box_art_url: str) -> Optional[str]:
        """Download and cache a category's box art image"""
        return await self.category_service.download_category_image(category_name, box_art_url)

    def get_cached_category_image(self, category_name: str) -> Optional[str]:
        """Get cached category image path"""
        return self.category_service.get_cached_category_image(category_name)

    async def update_category_image(self, category_name: str, box_art_url: str) -> bool:
        """Update a category's image"""
        return await self.category_service.update_category_image(category_name, box_art_url)

    async def sync_all_category_images(self) -> Dict[str, int]:
        """Sync all category images"""
        return await self.category_service.sync_all_category_images()

    async def bulk_sync_categories(self, category_data: List[Dict]) -> Dict[str, int]:
        """Bulk sync category images"""
        return await self.category_service.bulk_sync_categories(category_data)

    # Stream Artwork Methods (delegate to StreamArtworkService)
    
    async def download_stream_artwork(self, stream_id: int, streamer_id: int, thumbnail_url: str) -> Optional[str]:
        """Download and cache stream artwork"""
        return await self.artwork_service.download_stream_artwork(stream_id, streamer_id, thumbnail_url)

    def get_cached_stream_artwork(self, stream_id: int, streamer_id: int) -> Optional[str]:
        """Get cached stream artwork path"""
        return self.artwork_service.get_cached_stream_artwork(stream_id, streamer_id)

    async def update_stream_artwork(self, stream_id: int, thumbnail_url: str) -> bool:
        """Update a stream's artwork"""
        return await self.artwork_service.update_stream_artwork(stream_id, thumbnail_url)

    async def sync_stream_artwork(self, stream_ids: List[int] = None) -> Dict[str, int]:
        """Sync stream artwork"""
        return await self.artwork_service.sync_stream_artwork(stream_ids)

    async def bulk_download_artwork(self, artwork_data: List[Dict]) -> Dict[str, int]:
        """Bulk download stream artwork"""
        return await self.artwork_service.bulk_download_artwork(artwork_data)

    # Statistics and Maintenance Methods
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        profile_stats = self.profile_service.get_profile_cache_stats()
        category_stats = self.category_service.get_category_cache_stats()
        artwork_stats = self.artwork_service.get_artwork_cache_stats()
        
        return {
            "profiles": profile_stats,
            "categories": category_stats,
            "artwork": artwork_stats,
            "total_cached": (
                profile_stats.get("cached_profiles", 0) +
                category_stats.get("cached_categories", 0) +
                artwork_stats.get("cached_artworks", 0)
            ),
            "total_failed": (
                profile_stats.get("failed_downloads", 0) +
                category_stats.get("failed_downloads", 0) +
                artwork_stats.get("failed_downloads", 0)
            )
        }

    async def cleanup_unused_images(self) -> Dict[str, int]:
        """Clean up unused images from all services"""
        profile_cleaned = await self.profile_service.cleanup_unused_profile_images()
        category_cleaned = await self.category_service.cleanup_unused_category_images()
        artwork_cleaned = await self.artwork_service.cleanup_unused_artwork()
        
        return {
            "profiles_cleaned": profile_cleaned,
            "categories_cleaned": category_cleaned,
            "artwork_cleaned": artwork_cleaned,
            "total_cleaned": profile_cleaned + category_cleaned + artwork_cleaned
        }

    async def cleanup_old_artwork(self, days_old: int = 30) -> int:
        """Clean up old artwork files"""
        return await self.artwork_service.cleanup_old_artwork(days_old)

    # Legacy bulk methods for compatibility
    
    async def bulk_download_from_db(self) -> Dict[str, int]:
        """Legacy method - bulk download all images from database"""
        profile_stats = await self.sync_all_profile_images()
        category_stats = await self.sync_all_category_images()
        artwork_stats = await self.sync_stream_artwork()
        
        return {
            "profiles": profile_stats,
            "categories": category_stats,
            "artwork": artwork_stats
        }

    async def sync_all_images(self) -> Dict[str, Any]:
        """Sync all types of images"""
        return await self.bulk_download_from_db()


# Create a global instance for backward compatibility
unified_image_service = UnifiedImageService()
