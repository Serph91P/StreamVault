"""Legacy image migration with scoped catalogue values and atomic publication."""

import asyncio
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.database import SessionLocal
from app.models import Streamer
from app.utils.async_db_utils import batch_process_items, run_in_thread_pool
from app.utils.file_utils import (
    sanitize_filename,
    safe_remove_directory,
    validate_directory_path,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationStreamer:
    id: int
    username: str


class ImageMigrationService:
    """Service to migrate images from old structure to new simplified structure"""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._session_factory = session_factory
        self.recordings_dir = (
            Path(settings.RECORDING_DIRECTORY) if settings else Path("/recordings")
        )
        self.old_images_dir = self.recordings_dir / ".images"
        self.old_artwork_dir = self.recordings_dir / ".artwork"

    def _streamers(self) -> list[MigrationStreamer]:
        with (self._session_factory or SessionLocal)() as session:
            return [
                MigrationStreamer(row.id, row.username)
                for row in session.query(Streamer.id, Streamer.username).all()
            ]

    async def migrate_all_images(self) -> dict[str, int]:
        """Migrate images from old structure to new structure."""
        stats = {
            "streamers_migrated": 0,
            "images_moved": 0,
            "duplicates_found": 0,
            "errors": 0,
            "directories_cleaned": 0,
        }
        try:
            streamers = await run_in_thread_pool(self._streamers)
            async for batch in batch_process_items(
                streamers, batch_size=5, max_concurrent=2
            ):
                async with asyncio.TaskGroup() as group:
                    tasks = [
                        group.create_task(
                            self.migrate_streamer_images(streamer),
                            name=f"streamvault:image-migration:{streamer.id}",
                        )
                        for streamer in batch
                    ]
                for task in tasks:
                    result = task.result()
                    stats["errors"] += result["errors"]
                    stats["images_moved"] += result["images_moved"]
                    stats["duplicates_found"] += result["duplicates_found"]
                    if not result["errors"]:
                        stats["streamers_migrated"] += 1
            cleanup = await self.cleanup_old_directories()
            stats["directories_cleaned"] = cleanup["directories_removed"]
        except Exception as error:
            logger.error("Error during image migration (%s)", type(error).__name__)
            stats["errors"] += 1
        if stats["errors"]:
            logger.warning("Migration completed with errors: %s", stats)
        else:
            logger.info("Migration completed: %s", stats)
        return stats

    async def migrate_streamer_images(
        self, streamer: MigrationStreamer
    ) -> dict[str, int]:
        try:
            return await run_in_thread_pool(self._migrate_streamer_images, streamer)
        except Exception as error:
            logger.error("Image migration failed (%s)", type(error).__name__)
            return {"images_moved": 0, "duplicates_found": 0, "errors": 1}

    def _migrate_streamer_images(self, streamer: MigrationStreamer) -> dict[str, int]:
        result = {"images_moved": 0, "duplicates_found": 0, "errors": 0}
        name = sanitize_filename(streamer.username)
        streamer_dir = self.recordings_dir / name
        if not validate_directory_path(streamer_dir, self.recordings_dir):
            result["errors"] += 1
            return result
        if not streamer_dir.exists():
            return result
        media_dir = self.recordings_dir / ".media"
        artwork_dir = media_dir / "artwork" / name
        profiles_dir, categories_dir = media_dir / "profiles", media_dir / "categories"
        directories = (media_dir, artwork_dir, profiles_dir, categories_dir)
        legacy_directories = (
            self.old_images_dir / "profiles",
            self.old_images_dir / "artwork" / name,
            self.old_artwork_dir / name,
        )
        if not all(
            validate_directory_path(path, self.recordings_dir)
            for path in (*directories, *legacy_directories)
        ):
            result["errors"] += 1
            return result
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        sources = [
            self.old_images_dir / "profiles" / f"streamer_{streamer.id}.jpg",
            self.old_images_dir / "artwork" / name / "poster.jpg",
            self.old_images_dir / "artwork" / name / "banner.jpg",
            self.old_images_dir / "artwork" / name / "fanart.jpg",
            self.old_artwork_dir / name / "poster.jpg",
            self.old_artwork_dir / name / "banner.jpg",
            self.old_artwork_dir / name / "fanart.jpg",
        ]
        targets = {
            filename: artwork_dir / filename
            for filename in ("poster.jpg", "banner.jpg", "fanart.jpg")
        }
        for source in sources:
            if not validate_directory_path(source, self.recordings_dir):
                result["errors"] += 1
                continue
            if not source.exists():
                continue
            target_name = (
                "poster.jpg" if source.name.startswith("streamer_") else source.name
            )
            target = targets.get(target_name)
            if target is None:
                continue
            try:
                if target.exists():
                    if (
                        self._files_are_identical(source, target)
                        or source.stat().st_mtime <= target.stat().st_mtime
                    ):
                        source.unlink()
                        result["duplicates_found"] += 1
                        continue
                with TemporaryDirectory(
                    dir=target.parent, prefix=".image-migration-"
                ) as temporary_directory:
                    staged = Path(temporary_directory) / target.name
                    shutil.copy2(source, staged)
                    if not self._files_are_identical(source, staged):
                        raise OSError("Staged image does not match source")
                    staged.replace(target)
                source.unlink()
                result["images_moved"] += 1
            except Exception as error:
                result["errors"] += 1
                logger.error("Image migration file failed (%s)", type(error).__name__)
        return result

    async def cleanup_old_directories(self) -> dict[str, int]:
        return await run_in_thread_pool(self._cleanup_old_directories)

    def _cleanup_old_directories(self) -> dict[str, int]:
        result = {"directories_removed": 0}
        for directory in (self.old_images_dir, self.old_artwork_dir):
            if directory.exists():
                try:
                    if self._is_directory_empty_recursive(directory):
                        if safe_remove_directory(directory, self.recordings_dir):
                            result["directories_removed"] += 1
                except Exception as error:
                    logger.error(
                        "Image migration cleanup failed (%s)", type(error).__name__
                    )
        return result

    def _files_are_identical(self, file1: Path, file2: Path) -> bool:
        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False
            with file1.open("rb") as first, file2.open("rb") as second:
                while True:
                    first_chunk, second_chunk = first.read(8192), second.read(8192)
                    if first_chunk != second_chunk:
                        return False
                    if not first_chunk:
                        return True
        except Exception as error:
            logger.error("Image comparison failed (%s)", type(error).__name__)
            return False

    def _is_directory_empty_recursive(self, directory: Path) -> bool:
        try:
            for item in directory.iterdir():
                if item.is_file():
                    return False
                if item.is_dir() and not self._is_directory_empty_recursive(item):
                    return False
            return True
        except Exception:
            return False


image_migration_service = ImageMigrationService()
