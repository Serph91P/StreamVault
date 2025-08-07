"""
StreamerImageService - Profile image downloading and caching

DEPRECATED: Use UnifiedImageService directly instead
This is just a wrapper around UnifiedImageService for backward compatibility.
"""

import logging
from typing import Optional
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")


class StreamerImageService:
    """Handles streamer profile image downloading and caching"""
    
    def __init__(self):
        self.image_service = unified_image_service

    async def download_profile_image(self, url: str, streamer_id: str) -> str:
        """Download and cache profile image using unified_image_service"""
        try:
            # Use unified_image_service for download
            result = await self.image_service.download_profile_image(int(streamer_id), url)
            if result:
                logger.info(f"Successfully cached profile image for streamer {streamer_id}")
                return result
            else:
                # Fallback to original URL if download fails
                logger.warning(f"Failed to cache profile image for streamer {streamer_id}, using original URL")
                return url
        except Exception as e:
            logger.error(f"Failed to cache profile image for streamer {streamer_id}: {e}")
            return url

    def get_cached_profile_image(self, streamer_id: int) -> Optional[str]:
        """Get cached profile image path for a streamer"""
        try:
            return self.image_service.get_cached_profile_image(streamer_id)
        except Exception as e:
            logger.error(f"Error getting cached profile image for streamer {streamer_id}: {e}")
            return None

    async def update_streamer_profile_image(self, streamer_id: int, profile_image_url: str) -> bool:
        """Update a streamer's profile image in cache and return success status"""
        try:
            result = await self.image_service.update_streamer_profile_image(streamer_id, profile_image_url)
            if result:
                logger.info(f"Successfully updated profile image for streamer {streamer_id}")
            else:
                logger.warning(f"Failed to update profile image for streamer {streamer_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating profile image for streamer {streamer_id}: {e}")
            return False

    async def refresh_profile_image(self, streamer_id: int, new_url: str) -> Optional[str]:
        """Refresh profile image with a new URL and return the cached path"""
        try:
            # Download the new image
            cached_path = await self.download_profile_image(new_url, str(streamer_id))
            
            if cached_path and cached_path != new_url:
                # Successfully cached
                logger.info(f"Refreshed profile image for streamer {streamer_id}")
                return cached_path
            else:
                # Use original URL if caching failed
                logger.warning(f"Could not refresh profile image for streamer {streamer_id}, using original URL")
                return new_url
        except Exception as e:
            logger.error(f"Error refreshing profile image for streamer {streamer_id}: {e}")
            return new_url

    async def sync_all_profile_images(self) -> dict:
        """Sync all profile images using the unified image service"""
        try:
            return await self.image_service.sync_all_profile_images()
        except Exception as e:
            logger.error(f"Error syncing all profile images: {e}")
            return {"downloaded": 0, "skipped": 0, "failed": 0}

    def get_profile_cache_stats(self) -> dict:
        """Get statistics about profile image cache"""
        try:
            return self.image_service.get_cache_stats().get("profiles", {})
        except Exception as e:
            logger.error(f"Error getting profile cache stats: {e}")
            return {"cached_profiles": 0, "failed_downloads": 0}

    async def cleanup_unused_profile_images(self) -> int:
        """Clean up unused profile images"""
        try:
            cleanup_stats = await self.image_service.cleanup_unused_images()
            return cleanup_stats.get("profiles_cleaned", 0)
        except Exception as e:
            logger.error(f"Error cleaning up profile images: {e}")
            return 0

    def is_cached_image(self, image_url: str) -> bool:
        """Check if an image URL is a cached local path"""
        return image_url and image_url.startswith('/recordings/.media/profiles/')

    def get_original_url_from_cached(self, cached_path: str) -> Optional[str]:
        """Extract original URL info from cached path (limited functionality)"""
        # This is a simple check - the unified image service doesn't store URL mappings
        # In a production system, you might want to store this mapping in the database
        if self.is_cached_image(cached_path):
            # Return None as we don't have reverse mapping without database lookup
            return None
        return cached_path

    async def validate_image_url(self, url: str) -> bool:
        """Validate that an image URL is accessible"""
        try:
            if not url or not url.startswith('http'):
                return False
            
            # Use the download service to test if the URL is accessible
            session = await self.image_service.download_service.get_session()
            async with session.head(url) as response:
                content_type = response.headers.get('content-type', '')
                return response.status == 200 and 'image' in content_type
        except Exception as e:
            logger.debug(f"Image URL validation failed for {url}: {e}")
            return False

    async def get_image_dimensions(self, url: str) -> Optional[tuple]:
        """Get image dimensions if possible (basic implementation)"""
        try:
            # This would require additional image processing libraries
            # For now, return None - could be extended with PIL/Pillow
            logger.debug(f"Image dimensions requested for {url}, but not implemented")
            return None
        except Exception as e:
            logger.error(f"Error getting image dimensions for {url}: {e}")
            return None

    async def close(self):
        """Close the image service resources"""
        try:
            await self.image_service.close()
        except Exception as e:
            logger.error(f"Error closing image service: {e}")
