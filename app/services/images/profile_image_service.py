"""
ProfileImageService - Streamer profile image management

Extracted from unified_image_service.py God Class
Handles downloading, caching, and serving of streamer profile images.
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Streamer
from .image_download_service import ImageDownloadService

logger = logging.getLogger("streamvault")


class ProfileImageService:
    """Handles streamer profile image management"""
    
    def __init__(self, download_service: Optional[ImageDownloadService] = None):
        self.download_service = download_service or ImageDownloadService()
        self._profile_cache: Dict[str, str] = {}
        self.profiles_dir = None
        self._load_existing_cache()
    
    def _ensure_profiles_dir(self):
        """Ensure profiles directory exists"""
        if self.profiles_dir is None:
            try:
                images_base_dir = self.download_service.get_images_base_dir()
                self.profiles_dir = images_base_dir / "profiles"
                self.profiles_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to initialize profiles directory: {e}")
                # Fallback to a temporary path
                self.profiles_dir = Path(tempfile.gettempdir()) / "profiles"
                self.profiles_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_twitch_id_for_streamer(self, streamer_id: int) -> Optional[str]:
        """Get Twitch ID for a streamer by internal ID"""
        try:
            with SessionLocal() as db:
                from app.models import Streamer
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                return streamer.twitch_id if streamer else None
        except Exception as e:
            logger.error(f"Error getting Twitch ID for streamer {streamer_id}: {e}")
            return None
    
    def _extract_streamer_id_from_filename(self, image_file: Path) -> Optional[str]:
        """Extract streamer ID from profile image filename (supports both old and new formats)"""
        if image_file.stem.startswith("profile_avatar_"):
            return image_file.stem.replace("profile_avatar_", "")
        elif image_file.stem.startswith("streamer_"):
            return image_file.stem.replace("streamer_", "")
        else:
            return None  # File doesn't match expected patterns
    
    def _load_existing_cache(self):
        """Load information about already cached profile images"""
        try:
            self._ensure_profiles_dir()
            
            if self.profiles_dir and self.profiles_dir.exists():
                for image_file in self.profiles_dir.glob("*.jpg"):
                    extracted_id = self._extract_streamer_id_from_filename(image_file)
                    if extracted_id is None:
                        continue  # Skip files that don't match expected patterns
                    
                    # Convert to internal streamer ID for cache key
                    internal_id = self._get_internal_id_for_extracted_id(extracted_id)
                    if internal_id:
                        relative_path = f"/data/images/profiles/{image_file.name}"
                        self._profile_cache[str(internal_id)] = relative_path
            
            logger.info(f"Loaded profile image cache: {len(self._profile_cache)} profiles")
        except Exception as e:
            logger.error(f"Error loading profile image cache: {e}")

    def _get_internal_id_for_extracted_id(self, extracted_id: str) -> Optional[int]:
        """Convert extracted ID (could be internal ID or Twitch ID) to internal streamer ID"""
        try:
            with SessionLocal() as db:
                from app.models import Streamer
                
                # First try as internal ID (for old files)
                if extracted_id.isdigit():
                    streamer = db.query(Streamer).filter(Streamer.id == int(extracted_id)).first()
                    if streamer:
                        return streamer.id
                
                # Then try as Twitch ID (for new files)
                streamer = db.query(Streamer).filter(Streamer.twitch_id == extracted_id).first()
                if streamer:
                    return streamer.id
                    
                return None
        except Exception as e:
            logger.error(f"Error converting extracted ID {extracted_id} to internal ID: {e}")
            return None

    async def download_profile_image(self, streamer_id: int, profile_image_url: str) -> Optional[str]:
        """
        Download and cache a streamer's profile image
        
        Args:
            streamer_id: ID of the streamer
            profile_image_url: URL of the profile image
            
        Returns:
            Relative path to the cached image or None if failed
        """
        self._ensure_profiles_dir()
            
        if not profile_image_url:
            return None
            
        # Get the Twitch ID for proper filename
        twitch_id = self._get_twitch_id_for_streamer(streamer_id)
        if not twitch_id:
            logger.warning(f"Could not find Twitch ID for streamer {streamer_id}")
            return None
            
        # Check if already cached
        streamer_id_str = str(streamer_id)
        if streamer_id_str in self._profile_cache:
            return self._profile_cache[streamer_id_str]
            
        # Skip if previously failed
        if self.download_service.is_download_failed(profile_image_url):
            return None
            
        try:
            filename = f"profile_avatar_{twitch_id}.jpg"
            # Ensure profiles directory is properly initialized
            if self.profiles_dir is None:
                logger.error("Profiles directory not initialized")
                return None
            file_path = self.profiles_dir / filename
            
            success = await self.download_service.download_image(profile_image_url, file_path)
            if success:
                relative_path = f"/data/images/profiles/{filename}"
                self._profile_cache[streamer_id_str] = relative_path
                logger.info(f"Successfully cached profile image for streamer {streamer_id}")
                return relative_path
            else:
                logger.warning(f"Failed to download profile image for streamer {streamer_id}")
                self.download_service.mark_download_failed(profile_image_url)
                return None
                
        except Exception as e:
            logger.error(f"Error downloading profile image for streamer {streamer_id}: {e}")
            self.download_service.mark_download_failed(profile_image_url)
            return None

    def get_cached_profile_image(self, streamer_id: int) -> Optional[str]:
        """Get cached profile image path for a streamer"""
        return self._profile_cache.get(str(streamer_id))

    async def update_streamer_profile_image(self, streamer_id: int, profile_image_url: str) -> bool:
        """Update a streamer's profile image in database and cache"""
        try:
            # Download the image
            cached_path = await self.download_profile_image(streamer_id, profile_image_url)
            
            if cached_path:
                # Update database
                with SessionLocal() as db:
                    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                    if streamer:
                        streamer.profile_image_url = cached_path
                        db.commit()
                        logger.info(f"Updated profile image for streamer {streamer_id}")
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"Error updating profile image for streamer {streamer_id}: {e}")
            return False

    async def sync_all_profile_images(self) -> Dict[str, int]:
        """Sync all profile images for all streamers"""
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        
        try:
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                
                for streamer in streamers:
                    if streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
                        # This is a Twitch URL, download and cache it
                        cached_path = await self.download_profile_image(streamer.id, streamer.profile_image_url)
                        if cached_path:
                            # Update to use cached path
                            streamer.profile_image_url = cached_path
                            stats["downloaded"] += 1
                        else:
                            stats["failed"] += 1
                    else:
                        stats["skipped"] += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error syncing profile images: {e}")
            
        logger.info(f"Profile image sync completed: {stats}")
        return stats

    def get_profile_cache_stats(self) -> Dict[str, int]:
        """Get statistics about profile image cache"""
        return {
            "cached_profiles": len(self._profile_cache),
            "failed_downloads": len([url for url in self.download_service._failed_downloads if 'profile' in url])
        }

    async def cleanup_unused_profile_images(self) -> int:
        """Remove profile images that are no longer associated with any streamer"""
        cleaned_count = 0
        
        try:
            self._ensure_profiles_dir()
            
            # Get all streamer IDs from database
            with SessionLocal() as db:
                active_streamer_ids = set(str(s.id) for s in db.query(Streamer.id).all())
            
            # Check cached images (both old and new format)
            if self.profiles_dir is None:
                logger.error("Profiles directory not initialized for cleanup")
                return cleaned_count
            for image_file in self.profiles_dir.glob("*.jpg"):
                streamer_id = self._extract_streamer_id_from_filename(image_file)
                if streamer_id is None:
                    continue  # Skip files that don't match expected patterns
                
                if streamer_id not in active_streamer_ids:
                    try:
                        image_file.unlink()
                        # Remove from cache
                        self._profile_cache.pop(streamer_id, None)
                        cleaned_count += 1
                        logger.info(f"Removed unused profile image: {image_file.name}")
                    except Exception as e:
                        logger.error(f"Error removing profile image {image_file}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during profile image cleanup: {e}")
            
        return cleaned_count

    async def close(self):
        """Close the download service"""
        await self.download_service.close()
