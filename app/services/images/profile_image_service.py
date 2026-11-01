"""
ProfileImageService - Streamer profile image management

Extracted from unified_image_service.py God Class
Handles downloading, caching, and serving of streamer profile images.
"""

import logging
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from typing import Dict, Optional
from cachetools import TTLCache
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Streamer
from .image_download_service import ImageDownloadService
from app.config.constants import CACHE_CONFIG
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


class ProfileImageService:
    """Handles streamer profile image management"""

    def __init__(
        self,
        download_service: Optional[ImageDownloadService] = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._session_factory = session_factory
        self._cache_lock = RLock()
        self.download_service = download_service or ImageDownloadService()
        # TTLCache for profile images (prevents memory leaks with automatic expiration)
        self._profile_cache: TTLCache = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE, ttl=CACHE_CONFIG.IMAGE_CACHE_TTL
        )
        self._profile_sources: TTLCache = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE, ttl=CACHE_CONFIG.IMAGE_CACHE_TTL
        )
        self.profiles_dir = None
        self._cache_loaded = False
        # Don't load cache immediately during initialization - defer until first use

    def _sessions(self) -> Session:
        return (self._session_factory or SessionLocal)()

    def _ensure_profiles_dir(self):
        if self.profiles_dir is None:
            directory = self.download_service.get_images_base_dir() / "profiles"
            directory.mkdir(parents=True, exist_ok=True)
            self.profiles_dir = directory

    def _get_twitch_id_for_streamer(self, streamer_id: int) -> Optional[str]:
        """Get Twitch ID for a streamer by internal ID"""
        try:
            with self._sessions() as db:
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

    def _ensure_cache_loaded(self):
        with self._cache_lock:
            self._ensure_cache_loaded_locked()

    def _ensure_cache_loaded_locked(self):
        """Ensure cache is loaded, but only if database is available"""
        if self._cache_loaded:
            return

        try:
            # Test if database is ready by attempting a simple query
            with self._sessions() as db:
                # Try a simple query to check if streamers table exists
                # Use text() for raw SQL to avoid table reflection issues
                from sqlalchemy import text

                db.execute(text("SELECT 1 FROM streamers LIMIT 1")).fetchone()

            # Database is ready, load cache
            self._load_existing_cache()
            self._cache_loaded = True
        except Exception as e:
            # Database not ready yet, skip cache loading for now
            logger.debug(f"Database not ready for profile image cache loading: {e}")
            # Set a flag to indicate we tried but failed, so we don't spam logs
            if not hasattr(self, "_cache_load_attempted"):
                logger.info(
                    "Profile image cache loading deferred until database is ready"
                )
                self._cache_load_attempted = True

    def _load_existing_cache(self):
        with self._cache_lock:
            self._load_existing_cache_locked()

    def _load_existing_cache_locked(self):
        """Load information about already cached profile images"""
        # Disk filenames alone cannot prove which upstream URL produced the bytes.
        self._profile_sources.clear()
        try:
            self._ensure_profiles_dir()

            if self.profiles_dir and self.profiles_dir.exists():
                for image_file in self.profiles_dir.glob("*.jpg"):
                    extracted_id = self._extract_streamer_id_from_filename(image_file)
                    if extracted_id is None:
                        continue  # Skip files that don't match expected patterns

                    # Convert to internal streamer ID for cache key
                    # Only try database lookup if streamers table exists
                    try:
                        internal_id = self._get_internal_id_for_extracted_id(
                            extracted_id
                        )
                        if internal_id:
                            relative_path = (
                                f"/recordings/.media/profiles/{image_file.name}"
                            )
                            self._profile_cache[str(internal_id)] = relative_path
                    except Exception as db_error:
                        # Database not ready, use extracted_id as fallback key
                        logger.debug(
                            f"Using extracted ID {extracted_id} as cache key due to DB error: {db_error}"
                        )
                        relative_path = f"/recordings/.media/profiles/{image_file.name}"
                        self._profile_cache[str(extracted_id)] = relative_path

            logger.info(
                f"Loaded profile image cache: {len(self._profile_cache)} profiles"
            )
        except Exception as e:
            logger.error(f"Error loading profile image cache: {e}")

    def _get_internal_id_for_extracted_id(self, extracted_id: str) -> Optional[int]:
        """Convert extracted ID (could be internal ID or Twitch ID) to internal streamer ID"""
        try:
            with self._sessions() as db:
                from app.models import Streamer

                # First try as internal ID (for old files)
                if extracted_id.isdigit():
                    streamer = (
                        db.query(Streamer)
                        .filter(Streamer.id == int(extracted_id))
                        .first()
                    )
                    if streamer:
                        return streamer.id

                # Then try as Twitch ID (for new files)
                streamer = (
                    db.query(Streamer)
                    .filter(Streamer.twitch_id == extracted_id)
                    .first()
                )
                if streamer:
                    return streamer.id

                return None
        except Exception as e:
            logger.error(
                f"Error converting extracted ID {extracted_id} to internal ID: {e}"
            )
            return None

    def _cached_profile_for_source(
        self, streamer_id: str, source: str
    ) -> Optional[str]:
        self._ensure_cache_loaded()
        with self._cache_lock:
            if self._profile_sources.get(streamer_id) == source:
                return self._profile_cache.get(streamer_id)
            return None

    async def download_profile_image(
        self, streamer_id: int, profile_image_url: str
    ) -> Optional[str]:
        """
        Download and cache a streamer's profile image

        Args:
            streamer_id: ID of the streamer
            profile_image_url: URL of the profile image

        Returns:
            Relative path to the cached image or None if failed
        """
        await run_in_thread_pool(self._ensure_profiles_dir)

        if not profile_image_url:
            return None

        # Get the Twitch ID for proper filename
        twitch_id = await run_in_thread_pool(
            self._get_twitch_id_for_streamer, streamer_id
        )
        if not twitch_id:
            logger.warning(f"Could not find Twitch ID for streamer {streamer_id}")
            return None

        # Check if already cached
        streamer_id_str = str(streamer_id)
        cached = await run_in_thread_pool(
            self._cached_profile_for_source, streamer_id_str, profile_image_url
        )
        if cached is not None:
            return cached

        try:
            filename = f"profile_avatar_{twitch_id}.jpg"
            # Ensure profiles directory is properly initialized
            if self.profiles_dir is None:
                logger.error("Profiles directory not initialized")
                return None
            file_path = await run_in_thread_pool(
                self.download_service._resolve_destination_path,
                self.profiles_dir / filename,
            )
            relative_path = f"/recordings/.media/profiles/{filename}"
            staging = ExitStack()

            def prepare_staging() -> Path:
                directory = TemporaryDirectory(dir=file_path.parent, prefix=".profile-")
                staging.callback(directory.cleanup)
                return Path(directory.name) / filename

            try:
                staged_path = await run_in_thread_pool(prepare_staging)
                success = await self.download_service.download_image(
                    profile_image_url, staged_path, retry_failed=True
                )

                def publish() -> bool:
                    if not staged_path.stat().st_size:
                        return False
                    with self._cache_lock:
                        staged_path.replace(file_path)
                        self._profile_cache[streamer_id_str] = relative_path
                        self._profile_sources[streamer_id_str] = profile_image_url
                    return True

                if success:
                    success = await run_in_thread_pool(publish)
            finally:
                await run_in_thread_pool(staging.close)
            if success:
                logger.info(
                    f"Successfully cached profile image for streamer {streamer_id}"
                )
                return relative_path
            else:
                logger.warning(
                    f"Failed to download profile image for streamer {streamer_id}"
                )
                return None

        except Exception as e:
            logger.error(
                f"Error downloading profile image for streamer {streamer_id}: {e}"
            )
            return None

    def get_cached_profile_image(self, streamer_id: int) -> Optional[str]:
        """Get cached profile image path for a streamer"""
        self._ensure_cache_loaded()
        with self._cache_lock:
            return self._profile_cache.get(str(streamer_id))

    def _persist_profile_paths(self, updates: list[tuple[int, str]]) -> set[int]:
        with self._sessions() as db:
            changed: set[int] = set()
            for streamer_id, path in updates:
                changed.update(
                    db.execute(
                        update(Streamer)
                        .where(Streamer.id == streamer_id)
                        .values(profile_image_url=path)
                        .returning(Streamer.id)
                    )
                    .scalars()
                    .all()
                )
            db.commit()
            return changed

    async def update_streamer_profile_image(
        self, streamer_id: int, profile_image_url: str
    ) -> bool:
        """Download first, then persist using a separate closed worker transaction."""
        try:
            cached_path = await self.download_profile_image(
                streamer_id, profile_image_url
            )
            if cached_path:
                changed = await run_in_thread_pool(
                    self._persist_profile_paths, [(streamer_id, cached_path)]
                )
                return streamer_id in changed
        except Exception as error:
            logger.error("Profile image update failed: %s", type(error).__name__)
        return False

    def _profile_snapshot(self) -> list[tuple[int, str | None]]:
        with self._sessions() as db:
            return [
                (row.id, row.profile_image_url)
                for row in db.query(Streamer.id, Streamer.profile_image_url).all()
            ]

    async def sync_all_profile_images(self) -> Dict[str, int]:
        """Keep only scalar snapshots while performing provider I/O."""
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        try:
            snapshot = await run_in_thread_pool(self._profile_snapshot)
            updates: list[tuple[int, str]] = []
            for streamer_id, source in snapshot:
                if source and source.startswith("http"):
                    cached_path = await self.download_profile_image(streamer_id, source)
                    if cached_path:
                        updates.append((streamer_id, cached_path))
                    else:
                        stats["failed"] += 1
                else:
                    stats["skipped"] += 1
            changed = await run_in_thread_pool(self._persist_profile_paths, updates)
            stats["downloaded"] = len(changed)
            stats["failed"] += len(updates) - len(changed)
        except Exception as error:
            logger.error("Profile image sync failed: %s", type(error).__name__)
        logger.info("Profile image sync completed: %s", stats)
        return stats

    def get_profile_cache_stats(self) -> Dict[str, int]:
        """Get statistics about profile image cache"""
        self._ensure_cache_loaded()
        with self._cache_lock:
            return {
                "cached_profiles": len(self._profile_cache),
                "failed_downloads": sum(
                    "profile" in url
                    for url in tuple(self.download_service._failed_downloads)
                ),
            }

    async def cleanup_unused_profile_images(self) -> int:
        return await run_in_thread_pool(self._cleanup_unused_profile_images)

    def _cleanup_unused_profile_images(self) -> int:
        """Remove profile images that are no longer associated with any streamer"""
        cleaned_count = 0

        try:
            self._ensure_profiles_dir()

            # Get all streamer IDs from database
            with self._sessions() as db:
                rows = db.query(Streamer.id, Streamer.twitch_id).all()
                active_streamer_ids = {str(row.id) for row in rows}
                active_twitch_ids = {
                    str(row.twitch_id) for row in rows if row.twitch_id
                }

            # Check cached images (both old and new format)
            if self.profiles_dir is None:
                logger.error("Profiles directory not initialized for cleanup")
                return cleaned_count
            for image_file in self.profiles_dir.glob("*.jpg"):
                streamer_id = self._extract_streamer_id_from_filename(image_file)
                if streamer_id is None:
                    continue  # Skip files that don't match expected patterns

                active_ids = (
                    active_twitch_ids
                    if image_file.stem.startswith("profile_avatar_")
                    else active_streamer_ids
                )
                if streamer_id not in active_ids:
                    try:
                        with self._cache_lock:
                            image_file.unlink()
                            relative = f"/recordings/.media/profiles/{image_file.name}"
                            for key, cached_path in list(self._profile_cache.items()):
                                if cached_path == relative:
                                    self._profile_cache.pop(key, None)
                                    self._profile_sources.pop(key, None)
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
