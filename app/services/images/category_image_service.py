"""
CategoryImageService - Category/game image management

Extracted from unified_image_service.py God Class
Handles downloading, caching, and serving of category/game images.
"""

import asyncio
import logging
import os
from collections.abc import Callable
from threading import RLock
from sqlalchemy.orm import Session
from app.utils.async_db_utils import run_in_thread_pool
from pathlib import Path
from typing import Dict, Optional, List, Set
from cachetools import TTLCache
from app.database import SessionLocal
from app.models import Category
from .image_download_service import ImageDownloadService
from app.config.constants import CACHE_CONFIG

logger = logging.getLogger("streamvault")


class CategoryImageService:
    """Handles category/game image management"""

    # Constants
    DEFAULT_CATEGORY_IMAGE_PATH = "/api/media/categories/default-category.svg"

    def __init__(
        self,
        download_service: Optional[ImageDownloadService] = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._session_factory = session_factory
        self._cache_lock = RLock()
        self.download_service = download_service or ImageDownloadService()
        # TTLCache for category images (prevents memory leaks with automatic expiration)
        self._category_cache: TTLCache[str, str] = TTLCache(
            maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE, ttl=CACHE_CONFIG.IMAGE_CACHE_TTL
        )
        self._background_tasks: Set[asyncio.Task] = set()
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self.categories_dir: Path | None = None
        self._cache_loaded = False

    def _ensure_categories_dir(self):
        """Use only this owner's configured root, never shared temporary storage."""
        if self.categories_dir is None:
            directory = self.download_service.get_images_base_dir() / "categories"
            directory.mkdir(parents=True, exist_ok=True)
            self.categories_dir = directory

    def _load_existing_cache(self):
        with self._cache_lock:
            self._load_existing_cache_locked()

    def _load_existing_cache_locked(self):
        """Load information about already cached category images"""
        try:
            self._ensure_categories_dir()

            if self.categories_dir is not None and self.categories_dir.exists():
                for image_file in self.categories_dir.glob("*.jpg"):
                    category_name = self._filename_to_category(image_file.stem)
                    if category_name:
                        self._category_cache[category_name] = (
                            f"/api/media/categories/{image_file.name}"
                        )

            logger.info(
                f"Loaded category image cache: {len(self._category_cache)} categories"
            )
            self._cache_loaded = True
        except Exception as e:
            logger.error(f"Error loading category image cache: {e}")
            # Cache is already initialized as TTLCache in __init__, just clear it
            self._category_cache.clear()

    def _filename_to_category(self, filename: str) -> Optional[str]:
        """Convert filename back to category name"""
        # For now, assume filename is the category name with special chars replaced
        # This is a simplified approach - in production you might want a mapping file
        return filename.replace("_", " ").replace("-", " ")

    def _category_image_path(self, category_name: str) -> Path:
        """Build a category image path contained by the categories directory."""
        normalized_name = category_name.replace("\\", "/") if category_name else ""
        name_parts = normalized_name.split("/")
        if (
            not category_name
            or normalized_name.startswith("/")
            or any(part in {".", ".."} for part in name_parts)
        ):
            raise ValueError("Invalid category name")

        safe_name = self.download_service.sanitize_filename(category_name)
        if not safe_name or not safe_name.strip("."):
            raise ValueError("Invalid category name")

        self._ensure_categories_dir()
        if self.categories_dir is None:
            raise ValueError("Categories directory is not initialized")

        categories_dir = os.path.realpath(os.fspath(self.categories_dir))
        destination = os.path.realpath(os.path.join(categories_dir, f"{safe_name}.jpg"))
        try:
            is_contained = (
                os.path.commonpath((categories_dir, destination)) == categories_dir
            )
        except ValueError:
            is_contained = False
        if not is_contained:
            raise ValueError("Category image path is outside the categories directory")
        return Path(destination)

    def _source_for_category(self, category_name: str) -> str | None:
        with (self._session_factory or SessionLocal)() as db:
            source = (
                db.query(Category.box_art_url)
                .filter(Category.name == category_name)
                .scalar()
            )
            return source if isinstance(source, str) else None

    def _prepare_download(
        self, category_name: str, source: str | None
    ) -> tuple[Path, str] | None:
        self._ensure_categories_dir()
        if not category_name:
            return None
        file_path = self._category_image_path(category_name)
        if self.categories_dir is None:
            raise ValueError("Categories directory is not initialized")
        categories_dir = os.path.realpath(os.fspath(self.categories_dir))
        destination = os.path.realpath(os.path.abspath(os.fspath(file_path)))
        if not destination.startswith(categories_dir + os.sep):
            raise ValueError("Category image path is outside the categories directory")
        source = source or self._source_for_category(category_name)
        return (Path(destination), source) if source else None

    def _cached_download(
        self, name: str, path: Path, source: str
    ) -> tuple[bool, str | None]:
        with self._cache_lock:
            if source.startswith("/api/media/categories/"):
                if path.exists():
                    self._category_cache[name] = source
                    return True, source
                return True, None
            cached = self._category_cache.get(name)
            return cached is not None, cached

    def _cache_category(self, name: str, path: str) -> None:
        with self._cache_lock:
            self._category_cache[name] = path

    async def download_category_image(
        self, category_name: str, box_art_url: str | None = None
    ) -> Optional[str]:
        """
        Download and cache a category's box art image

        Args:
            category_name: Name of the category/game
            box_art_url: URL of the box art image (optional, will fetch from database if not provided)

        Returns:
            Relative path to the cached image or None if failed
        """
        if self._closed:
            return None
        try:
            prepared = await run_in_thread_pool(
                self._prepare_download, category_name, box_art_url
            )
        except ValueError as error:
            logger.warning("Invalid category image path: %s", type(error).__name__)
            return None
        except Exception as error:
            logger.error("Category image preparation failed: %s", type(error).__name__)
            return None
        if prepared is None:
            return None
        file_path, box_art_url = prepared
        filename = file_path.name
        complete, cached = await run_in_thread_pool(
            self._cached_download, category_name, file_path, box_art_url
        )
        if complete:
            return cached

        # Skip if previously failed
        if self.download_service.is_download_failed(box_art_url):
            return None

        try:
            success = await self.download_service.download_image(box_art_url, file_path)
            if success:
                relative_path = f"/api/media/categories/{filename}"
                await run_in_thread_pool(
                    self._cache_category, category_name, relative_path
                )
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
        with self._cache_lock:
            return self._get_cached_category_image(category_name)

    def _get_cached_category_image(self, category_name: str) -> Optional[str]:
        """Blocking compatibility lookup; async callers use the worker boundary."""
        if not self._cache_loaded:
            self._load_existing_cache()
        # First check the memory cache (fastest)
        cached_path = self._category_cache.get(category_name)
        if cached_path:
            return cached_path

        # Check if we have a database entry and verify if file exists locally
        try:
            with (self._session_factory or SessionLocal)() as db:
                category = (
                    db.query(Category).filter(Category.name == category_name).first()
                )
                if category and category.box_art_url:
                    # If it's already a local path, check if file exists
                    if category.box_art_url.startswith("/api/media/categories/"):
                        try:
                            file_path = self._category_image_path(category_name)
                        except ValueError as e:
                            logger.warning(
                                f"Invalid category image path for {category_name}: {e}"
                            )
                            return None

                        if self.categories_dir is None:
                            return None
                        categories_dir = os.path.realpath(
                            os.fspath(self.categories_dir)
                        )
                        destination = os.path.realpath(
                            os.path.abspath(os.fspath(file_path))
                        )
                        if not destination.startswith(categories_dir + os.sep):
                            logger.warning(
                                f"Invalid category image path for {category_name}"
                            )
                            return None
                        file_path = Path(destination)

                        if file_path.exists():
                            # Cache it and return
                            self._category_cache[category_name] = category.box_art_url
                            return category.box_art_url

                    # If it's a Twitch URL, return None to trigger download via API
                    return None
        except Exception as e:
            logger.error(f"Error getting category from database: {e}")

        # No cached image and no database entry - return None for icon fallback
        return None

    async def get_cached_category_image_with_download(
        self, category_name: str
    ) -> Optional[str]:
        """Read in a closed worker scope; retain download tasks on this owner loop."""
        if self._closed:
            return None
        cached = await run_in_thread_pool(self.get_cached_category_image, category_name)
        if cached:
            return cached
        try:
            source = await run_in_thread_pool(self._source_for_category, category_name)
            if source and not self._closed:
                task = asyncio.create_task(
                    self._download_category_image_background(category_name, source),
                    name="streamvault:category-image-download",
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                return source
        except Exception as error:
            logger.error("Category image lookup failed: %s", type(error).__name__)
        return None

    async def _download_category_image_background(
        self, category_name: str, box_art_url: str
    ):
        """Background task to download category image"""
        try:
            cached_path = await self.download_category_image(category_name, box_art_url)
            if cached_path:
                logger.info(
                    f"Background download completed for category: {category_name}"
                )
            else:
                logger.warning(
                    f"Background download failed for category: {category_name}"
                )
        except Exception as e:
            logger.error(f"Error in background download for {category_name}: {e}")

    def _persist_categories(self, updates: list[tuple[str, str]]) -> set[str]:
        with (self._session_factory or SessionLocal)() as db:
            changed: set[str] = set()
            for name, path in updates:
                category = db.query(Category).filter(Category.name == name).first()
                if category:
                    category.box_art_url = path
                    changed.add(name)
            db.commit()
            return changed

    async def update_category_image(self, category_name: str, box_art_url: str) -> bool:
        """Publish an image before a separate closed catalogue transaction."""
        try:
            cached_path = await self.download_category_image(category_name, box_art_url)
            if cached_path:
                changed = await run_in_thread_pool(
                    self._persist_categories, [(category_name, cached_path)]
                )
                return category_name in changed
        except Exception as error:
            logger.error("Category image update failed: %s", type(error).__name__)
        return False

    def _category_sources(self) -> list[tuple[str, str | None]]:
        with (self._session_factory or SessionLocal)() as db:
            return [
                (row.name, row.box_art_url)
                for row in db.query(Category.name, Category.box_art_url).all()
            ]

    async def sync_all_category_images(self) -> Dict[str, int]:
        """Keep scalar source snapshots, never ORM rows, across HTTP."""
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        try:
            sources = await run_in_thread_pool(self._category_sources)
            updates: list[tuple[str, str]] = []
            for name, source in sources:
                if source and source.startswith("http"):
                    cached = await self.download_category_image(name, source)
                    if cached:
                        updates.append((name, cached))
                    else:
                        stats["failed"] += 1
                else:
                    stats["skipped"] += 1
            changed = await run_in_thread_pool(self._persist_categories, updates)
            stats["downloaded"] = len(changed)
            stats["failed"] += len(updates) - len(changed)
        except Exception as error:
            logger.error("Category image sync failed: %s", type(error).__name__)
        logger.info("Category image sync completed: %s", stats)
        return stats

    def _publish_bulk(
        self, entries: list[tuple[str, str | None, str, str | None]]
    ) -> dict[str, int]:
        stats = {"updated": 0, "downloaded": 0, "failed": 0}
        with (self._session_factory or SessionLocal)() as db:
            for name, twitch_id, source, cached in entries:
                category = db.query(Category).filter(Category.name == name).first()
                if not category:
                    category = Category(
                        name=name, twitch_id=twitch_id, box_art_url=source
                    )
                    db.add(category)
                    stats["updated"] += 1
                if source.startswith("http"):
                    if cached:
                        category.box_art_url = cached
                        stats["downloaded"] += 1
                    else:
                        stats["failed"] += 1
            db.commit()
        return stats

    async def bulk_sync_categories(self, category_data: List[Dict]) -> Dict[str, int]:
        """Perform provider I/O before the single catalogue publication transaction."""
        stats = {"updated": 0, "downloaded": 0, "failed": 0}
        try:
            entries: list[tuple[str, str | None, str, str | None]] = []
            for information in category_data:
                name, source = information.get("name"), information.get("box_art_url")
                if (
                    not isinstance(name, str)
                    or not name
                    or not isinstance(source, str)
                    or not source
                ):
                    continue
                twitch_id = information.get("id")
                cached = (
                    await self.download_category_image(name, source)
                    if source.startswith("http")
                    else None
                )
                entries.append(
                    (
                        name,
                        str(twitch_id) if twitch_id is not None else None,
                        source,
                        cached,
                    )
                )
            stats = await run_in_thread_pool(self._publish_bulk, entries)
        except Exception as error:
            logger.error("Bulk category image sync failed: %s", type(error).__name__)
        logger.info("Bulk category sync completed: %s", stats)
        return stats

    def get_category_cache_stats(self) -> Dict[str, int]:
        with self._cache_lock:
            return self._get_category_cache_stats()

    def _get_category_cache_stats(self) -> Dict[str, int]:
        """Get statistics about category image cache"""
        if not self._cache_loaded:
            self._load_existing_cache()
        return {
            "cached_categories": len(self._category_cache),
            "failed_downloads": len(
                [
                    url
                    for url in self.download_service._failed_downloads
                    if "category" in url or "box_art" in url
                ]
            ),
        }

    async def cleanup_unused_category_images(self) -> int:
        return await run_in_thread_pool(self._cleanup_unused_category_images)

    def _cleanup_unused_category_images(self) -> int:
        """Remove only filenames not associated with an authoritative category."""
        cleaned_count = 0

        try:
            self._ensure_categories_dir()

            # Get all category names from database
            with (self._session_factory or SessionLocal)() as db:
                active_filenames = {
                    self.download_service.sanitize_filename(row.name) + ".jpg"
                    for row in db.query(Category.name).all()
                }

            if self.categories_dir is None:
                return 0
            for image_file in self.categories_dir.glob("*.jpg"):
                if image_file.name not in active_filenames:
                    try:
                        with self._cache_lock:
                            image_file.unlink()
                            relative_path = f"/api/media/categories/{image_file.name}"
                            for key, cached in list(self._category_cache.items()):
                                if cached == relative_path:
                                    self._category_cache.pop(key, None)
                        cleaned_count += 1
                        logger.info(f"Removed unused category image: {image_file.name}")
                    except Exception as e:
                        logger.error(f"Error removing category image {image_file}: {e}")

        except Exception as e:
            logger.error(f"Error during category image cleanup: {e}")

        return cleaned_count

    async def _finish_close(self) -> None:
        tasks = tuple(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()
        await self.download_service.close()

    async def close(self) -> None:
        """Drain only this owner's producers before closing its transport."""
        self._closed = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(
                self._finish_close(), name="streamvault:category-images-close"
            )
        task = self._close_task
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()
            raise
