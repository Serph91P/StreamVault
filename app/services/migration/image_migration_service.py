"""
Image Migration Service

Migrates images from old directory structure to new simplified structure.
Cleans up old directories and prevents duplicates.
"""

import shutil
import logging
import asyncio
from pathlib import Path
from typing import Dict, Optional, Awaitable, Any

from app.models import Streamer
from app.utils.file_utils import sanitize_filename, safe_remove_directory

logger = logging.getLogger(__name__)


class ImageMigrationService:
    """Service to migrate images from old structure to new simplified structure"""

    def __init__(self):
        # Hardcoded Docker path - always /recordings in container
        self.recordings_dir = Path("/recordings")
        self.old_images_dir = self.recordings_dir / ".images"
        self.old_artwork_dir = self.recordings_dir / ".artwork"

    async def migrate_all_images(self) -> Dict[str, int]:
        """
        Migrate all images from old structure to new structure
        Returns statistics about migration
        """
        stats = {
            "streamers_migrated": 0,
            "images_moved": 0,
            "duplicates_found": 0,
            "errors": 0,
            "directories_cleaned": 0,
        }

        try:
            # Get all streamers from database using async session management
            from app.utils.async_db_utils import get_all_streamers, batch_process_items

            streamers = await get_all_streamers()

            # Process streamers in batches for better performance
            async for batch in batch_process_items(streamers, batch_size=5, max_concurrent=2):
                # Create task-to-streamer mapping for O(1) lookup performance
                task_to_streamer_map: Dict[Awaitable[Any], Streamer] = {}
                tasks = []

                for streamer in batch:
                    try:
                        task = asyncio.create_task(self.migrate_streamer_images(streamer))
                        task_to_streamer_map[task] = streamer
                        tasks.append(task)
                    except Exception as e:
                        logger.error(f"Error creating migration task for streamer {streamer.username}: {e}")
                        stats["errors"] += 1

                # Process tasks as they complete to avoid memory buildup
                if tasks:
                    for completed_task in asyncio.as_completed(tasks):
                        try:
                            result = await completed_task
                            # O(1) lookup for streamer associated with completed task
                            # Note: asyncio.as_completed() returns the original task objects,
                            # so the mapping lookup works correctly
                            streamer = self._get_streamer_for_task(task_to_streamer_map, completed_task)
                            streamer_name = streamer.username if streamer else "Unknown"

                            stats["streamers_migrated"] += 1
                            stats["images_moved"] += result["images_moved"]
                            stats["duplicates_found"] += result["duplicates_found"]

                            logger.debug(f"Successfully migrated images for streamer {streamer_name}")
                        except Exception as e:
                            # O(1) lookup for streamer associated with failed task
                            # Note: asyncio.as_completed() returns the original task objects,
                            # so the mapping lookup works correctly
                            streamer = self._get_streamer_for_task(task_to_streamer_map, completed_task)
                            streamer_name = streamer.username if streamer else "Unknown"
                            logger.error(f"Error migrating images for streamer {streamer_name}: {e}")
                            stats["errors"] += 1

            # Clean up old directories
            cleanup_result = await self.cleanup_old_directories()
            stats["directories_cleaned"] = cleanup_result["directories_removed"]

            logger.info(f"Migration completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error during image migration: {e}")
            stats["errors"] += 1
            return stats

    async def migrate_streamer_images(self, streamer: Streamer) -> Dict[str, int]:
        """
        Migrate images for a specific streamer
        """
        result = {"images_moved": 0, "duplicates_found": 0}

        # Get streamer directory
        streamer_dir = self.recordings_dir / sanitize_filename(streamer.username)

        if not streamer_dir.exists():
            logger.warning(f"Streamer directory not found: {streamer_dir}")
            return result

        # Create .media directory structure (hidden from media servers)
        media_dir = self.recordings_dir / ".media"
        artwork_dir = media_dir / "artwork" / sanitize_filename(streamer.username)
        profiles_dir = media_dir / "profiles"
        categories_dir = media_dir / "categories"

        # Ensure directories exist
        for directory in [media_dir, artwork_dir, profiles_dir, categories_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Migration paths to check
        migration_sources = [
            # Old .images structure
            self.old_images_dir / "profiles" / f"streamer_{streamer.id}.jpg",
            self.old_images_dir / "artwork" / sanitize_filename(streamer.username) / "poster.jpg",
            self.old_images_dir / "artwork" / sanitize_filename(streamer.username) / "banner.jpg",
            self.old_images_dir / "artwork" / sanitize_filename(streamer.username) / "fanart.jpg",
            # Old .artwork structure
            self.old_artwork_dir / sanitize_filename(streamer.username) / "poster.jpg",
            self.old_artwork_dir / sanitize_filename(streamer.username) / "banner.jpg",
            self.old_artwork_dir / sanitize_filename(streamer.username) / "fanart.jpg",
        ]

        # Target files in .media directory structure
        target_files = {
            "poster.jpg": artwork_dir / "poster.jpg",
            "banner.jpg": artwork_dir / "banner.jpg",
            "fanart.jpg": artwork_dir / "fanart.jpg",
        }

        for source_path in migration_sources:
            if source_path.exists():
                # Determine target filename
                target_name = source_path.name
                if target_name.startswith("streamer_"):
                    target_name = "poster.jpg"  # Profile images become poster

                target_path = target_files.get(target_name)
                if target_path:
                    # Check for duplicates
                    if target_path.exists():
                        if self._files_are_identical(source_path, target_path):
                            logger.debug(f"Identical file found, removing source: {source_path}")
                            source_path.unlink()
                            result["duplicates_found"] += 1
                            continue
                        else:
                            # Keep newer file
                            if source_path.stat().st_mtime > target_path.stat().st_mtime:
                                logger.info(f"Replacing older file: {target_path}")
                                target_path.unlink()
                            else:
                                logger.info(f"Keeping newer target file, removing source: {source_path}")
                                source_path.unlink()
                                result["duplicates_found"] += 1
                                continue

                    # Move file
                    try:
                        shutil.move(str(source_path), str(target_path))
                        logger.info(f"Moved image: {source_path} -> {target_path}")
                        result["images_moved"] += 1
                    except Exception as e:
                        logger.error(f"Error moving file {source_path} to {target_path}: {e}")

        return result

    async def cleanup_old_directories(self) -> Dict[str, int]:
        """
        Remove old empty directories after migration
        """
        result = {"directories_removed": 0}

        directories_to_check = [self.old_images_dir, self.old_artwork_dir]

        for directory in directories_to_check:
            if directory.exists():
                try:
                    # Use safe directory removal with path validation
                    if self._is_directory_empty_recursive(directory):
                        if safe_remove_directory(directory, self.recordings_dir):
                            logger.info(f"Safely removed empty directory: {directory}")
                            result["directories_removed"] += 1
                        else:
                            logger.error(f"Failed to safely remove directory: {directory}")
                    else:
                        logger.warning(f"Directory not empty, keeping: {directory}")
                        # List remaining files for debugging
                        remaining_files = list(directory.rglob("*"))
                        logger.debug(f"Remaining files in {directory}: {remaining_files}")
                except Exception as e:
                    logger.error(f"Error removing directory {directory}: {e}")

        return result

    def _get_streamer_for_task(
        self, task_to_streamer_map: Dict[Awaitable[Any], Streamer], task: Awaitable[Any]
    ) -> Optional[Streamer]:
        """
        Helper function to get streamer associated with a task.
        Uses O(1) dictionary lookup instead of O(n) linear search.

        Args:
            task_to_streamer_map: Dictionary mapping awaitable objects (Tasks/Futures) to Streamer instances
            task: The awaitable object to look up (Task or Future from as_completed)

        Returns:
            The Streamer associated with the task, or None if not found
        """
        return task_to_streamer_map.get(task)

    def _files_are_identical(self, file1: Path, file2: Path) -> bool:
        """Check if two files are identical (same size and content)"""
        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False

            # Compare file content in chunks
            chunk_size = 8192
            with open(file1, "rb") as f1, open(file2, "rb") as f2:
                while True:
                    chunk1 = f1.read(chunk_size)
                    chunk2 = f2.read(chunk_size)
                    if chunk1 != chunk2:
                        return False
                    if not chunk1:  # End of file
                        return True
        except Exception as e:
            logger.error(f"Error comparing files {file1} and {file2}: {e}")
            return False

    def _is_directory_empty_recursive(self, directory: Path) -> bool:
        """Check if directory is empty or only contains empty subdirectories"""
        try:
            for item in directory.iterdir():
                if item.is_file():
                    return False
                elif item.is_dir():
                    if not self._is_directory_empty_recursive(item):
                        return False
            return True
        except Exception:
            return False


# Global instance
image_migration_service = ImageMigrationService()
