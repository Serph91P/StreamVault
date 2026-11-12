"""
BannerImageService - Streamer banner/offline image management

Handles downloading, caching, and serving of Twitch streamer banners (offline images).
These are displayed on profile pages and can be used in NFO files for media servers.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from sqlalchemy.orm import Session
from app.utils.async_db_utils import run_in_thread_pool
from typing import Dict, Optional
from cachetools import TTLCache
from app.database import SessionLocal
from app.models import Streamer
from .image_download_service import ImageDownloadService
from app.config.constants import CACHE_CONFIG

logger = logging.getLogger("streamvault")


class BannerImageService:
    """Handles streamer banner image management"""

    def __init__(
        self,
        download_service: Optional[ImageDownloadService] = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._session_factory = session_factory
        self._cache_lock = RLock()
        self.download_service = download_service or ImageDownloadService()
        # TTLCache for banner images
        self._banner_cache: TTLCache[int, str] = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE, ttl=CACHE_CONFIG.IMAGE_CACHE_TTL
        )
        self.banners_dir: Path | None = None
        self._cache_loaded = False

    def _ensure_banners_dir(self) -> None:
        """Create only this owner's configured storage root."""
        if self.banners_dir is None:
            directory = self.download_service.get_images_base_dir() / "banners"
            directory.mkdir(parents=True, exist_ok=True)
            self.banners_dir = directory

    def _load_existing_cache(self) -> None:
        with self._cache_lock:
            self._load_existing_cache_locked()

    def _load_existing_cache_locked(self) -> None:
        """Load existing banner images into cache"""
        if self._cache_loaded:
            return

        try:
            self._ensure_banners_dir()

            if not self.banners_dir or not self.banners_dir.exists():
                logger.warning("Banners directory does not exist, skipping cache load")
                self._cache_loaded = True
                return

            # Load from filesystem
            banner_files = list(self.banners_dir.glob("banner_*.jpg")) + list(
                self.banners_dir.glob("banner_*.png")
            )

            for banner_file in banner_files:
                try:
                    # Extract streamer_id from filename: banner_123.jpg -> 123
                    filename_parts = banner_file.stem.split("_")
                    if len(filename_parts) >= 2:
                        streamer_id = int(filename_parts[1])
                        self._banner_cache[streamer_id] = (
                            f"/data/images/banners/{banner_file.name}"
                        )
                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Could not parse banner filename {banner_file.name}: {e}"
                    )
                    continue

            logger.info(
                f"Loaded {len(self._banner_cache)} cached banners from filesystem"
            )
            self._cache_loaded = True

        except Exception as e:
            logger.error(f"Error loading banner cache: {e}")
            self._cache_loaded = True  # Mark as loaded even on error to prevent retries

    def _banner_path(self, streamer_id: int) -> Path:
        self._ensure_banners_dir()
        if self.banners_dir is None:
            raise RuntimeError("Banner storage unavailable")
        return self.banners_dir / f"banner_{streamer_id}.jpg"

    def _persist_banner(self, streamer_id: int, source: str, cached_url: str) -> None:
        with self._cache_lock:
            self._banner_cache[streamer_id] = cached_url
        with (self._session_factory or SessionLocal)() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                streamer.offline_image_url = cached_url
                streamer.original_offline_image_url = source
                db.commit()

    async def download_banner_image(
        self, streamer_id: int, offline_image_url: str
    ) -> Optional[str]:
        """Download and cache a streamer's banner image"""
        try:
            file_path = await run_in_thread_pool(self._banner_path, streamer_id)

            if not offline_image_url:
                logger.debug(f"No banner URL provided for streamer {streamer_id}")
                return None

            # Generate filename (hash used for cache validation in future)
            _ = self.download_service.create_filename_hash(offline_image_url)
            filename = file_path.name

            # Download image
            success = await self.download_service.download_image(
                offline_image_url, file_path
            )

            if success:
                cached_url = f"/data/images/banners/{filename}"
                await run_in_thread_pool(
                    self._persist_banner, streamer_id, offline_image_url, cached_url
                )

                return cached_url
            else:
                logger.error(f"Failed to download banner for streamer {streamer_id}")
                return None

        except Exception as e:
            logger.error(f"Error downloading banner for streamer {streamer_id}: {e}")
            return None

    def get_cached_banner_image(self, streamer_id: int) -> Optional[str]:
        """Get cached banner image URL"""
        self._load_existing_cache()
        with self._cache_lock:
            return self._banner_cache.get(streamer_id)

    def get_banner_image_url(
        self, streamer_id: int, original_url: Optional[str] = None
    ) -> Optional[str]:
        """Get banner image URL (cached or original)"""
        cached_url = self.get_cached_banner_image(streamer_id)
        if cached_url:
            return cached_url
        return original_url

    async def update_streamer_banner_image(
        self, streamer_id: int, offline_image_url: str
    ) -> bool:
        """Update a streamer's banner image"""
        try:
            cached_url = await self.download_banner_image(
                streamer_id, offline_image_url
            )
            return cached_url is not None
        except Exception as e:
            logger.error(f"Error updating banner for streamer {streamer_id}: {e}")
            return False

    def _banner_sources(self) -> list[tuple[int, str]]:
        with (self._session_factory or SessionLocal)() as db:
            return [
                (row.id, row.original_offline_image_url)
                for row in db.query(Streamer.id, Streamer.original_offline_image_url)
                .filter(
                    Streamer.original_offline_image_url.isnot(None),
                    Streamer.original_offline_image_url != "",
                )
                .all()
            ]

    async def sync_all_banner_images(self) -> Dict[str, int]:
        """Close the catalogue snapshot before any provider request."""
        stats = {"downloaded": 0, "failed": 0, "skipped": 0, "total": 0}
        try:
            sources = await run_in_thread_pool(self._banner_sources)
            stats["total"] = len(sources)
            for streamer_id, source in sources:
                cached = await run_in_thread_pool(
                    self.get_cached_banner_image, streamer_id
                )
                if cached:
                    stats["skipped"] += 1
                    continue
                if await self.download_banner_image(streamer_id, source):
                    stats["downloaded"] += 1
                else:
                    stats["failed"] += 1
        except Exception as error:
            logger.error("Banner sync failed: %s", type(error).__name__)
        logger.info("Banner sync completed: %s", stats)
        return stats

    async def cleanup_unused_banner_images(self) -> int:
        return await run_in_thread_pool(self._cleanup_unused_banner_images)

    def _cleanup_unused_banner_images(self) -> int:
        """Clean up banner images for streamers that no longer exist"""
        cleaned = 0

        try:
            self._ensure_banners_dir()

            if not self.banners_dir or not self.banners_dir.exists():
                return 0

            # Get all streamer IDs from database
            with (self._session_factory or SessionLocal)() as db:
                valid_ids = {s.id for s in db.query(Streamer.id).all()}

            # Check all banner files
            banner_files = list(self.banners_dir.glob("banner_*.jpg")) + list(
                self.banners_dir.glob("banner_*.png")
            )

            for banner_file in banner_files:
                try:
                    # Extract streamer_id from filename
                    filename_parts = banner_file.stem.split("_")
                    if len(filename_parts) >= 2:
                        streamer_id = int(filename_parts[1])

                        # Remove if streamer doesn't exist
                        if streamer_id not in valid_ids:
                            with self._cache_lock:
                                banner_file.unlink()
                                self._banner_cache.pop(streamer_id, None)
                            cleaned += 1
                            logger.info(f"Removed orphaned banner: {banner_file.name}")

                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Could not parse banner filename {banner_file.name}: {e}"
                    )
                    continue

            logger.info(f"Cleaned up {cleaned} orphaned banner images")

        except Exception as e:
            logger.error(f"Error cleaning up banners: {e}")

        return cleaned

    def get_banner_cache_stats(self) -> Dict[str, int]:
        """Get banner cache statistics"""
        self._load_existing_cache()

        with self._cache_lock:
            stats = {
                "cached_banners": len(self._banner_cache),
                "failed_downloads": len(self.download_service._failed_downloads),
            }

        # Count files on disk
        try:
            self._ensure_banners_dir()
            if self.banners_dir and self.banners_dir.exists():
                banner_files = list(self.banners_dir.glob("banner_*.jpg")) + list(
                    self.banners_dir.glob("banner_*.png")
                )
                stats["files_on_disk"] = len(banner_files)
            else:
                stats["files_on_disk"] = 0
        except Exception as e:
            logger.error(f"Error counting banner files: {e}")
            stats["files_on_disk"] = 0

        return stats
