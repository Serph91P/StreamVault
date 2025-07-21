"""
Image Migration Service

Migrates images from old directory structure to new simplified structure.
Cleans up old directories and prevents duplicates.
"""
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Streamer

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
            "directories_cleaned": 0
        }
        
        try:
            # Get all streamers from database using proper session management
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                
                for streamer in streamers:
                    try:
                        result = await self.migrate_streamer_images(streamer, db)
                        stats["streamers_migrated"] += 1
                        stats["images_moved"] += result["images_moved"]
                        stats["duplicates_found"] += result["duplicates_found"]
                    except Exception as e:
                        logger.error(f"Error migrating images for streamer {streamer.username}: {e}")
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
    
    async def migrate_streamer_images(self, streamer: Streamer, db: Session) -> Dict[str, int]:
        """
        Migrate images for a specific streamer
        """
        result = {
            "images_moved": 0,
            "duplicates_found": 0
        }
        
        # Get streamer directory
        streamer_dir = self.recordings_dir / self._sanitize_filename(streamer.username)
        
        if not streamer_dir.exists():
            logger.warning(f"Streamer directory not found: {streamer_dir}")
            return result
        
        # Create .media directory structure (hidden from media servers)
        media_dir = self.recordings_dir / ".media"
        artwork_dir = media_dir / "artwork" / self._sanitize_filename(streamer.username)
        profiles_dir = media_dir / "profiles"
        categories_dir = media_dir / "categories"
        
        # Ensure directories exist
        for directory in [media_dir, artwork_dir, profiles_dir, categories_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Migration paths to check
        migration_sources = [
            # Old .images structure
            self.old_images_dir / "profiles" / f"streamer_{streamer.id}.jpg",
            self.old_images_dir / "artwork" / self._sanitize_filename(streamer.username) / "poster.jpg",
            self.old_images_dir / "artwork" / self._sanitize_filename(streamer.username) / "banner.jpg",
            self.old_images_dir / "artwork" / self._sanitize_filename(streamer.username) / "fanart.jpg",
            
            # Old .artwork structure
            self.old_artwork_dir / self._sanitize_filename(streamer.username) / "poster.jpg",
            self.old_artwork_dir / self._sanitize_filename(streamer.username) / "banner.jpg",
            self.old_artwork_dir / self._sanitize_filename(streamer.username) / "fanart.jpg",
        ]
        
        # Target files in .media directory structure
        target_files = {
            "poster.jpg": artwork_dir / "poster.jpg",
            "banner.jpg": artwork_dir / "banner.jpg", 
            "fanart.jpg": artwork_dir / "fanart.jpg"
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
        
        directories_to_check = [
            self.old_images_dir,
            self.old_artwork_dir
        ]
        
        for directory in directories_to_check:
            if directory.exists():
                try:
                    # Check if directory is empty or only contains empty subdirectories
                    if self._is_directory_empty_recursive(directory):
                        shutil.rmtree(directory)
                        logger.info(f"Removed empty directory: {directory}")
                        result["directories_removed"] += 1
                    else:
                        logger.warning(f"Directory not empty, keeping: {directory}")
                        # List remaining files for debugging
                        remaining_files = list(directory.rglob("*"))
                        logger.debug(f"Remaining files in {directory}: {remaining_files}")
                except Exception as e:
                    logger.error(f"Error removing directory {directory}: {e}")
        
        return result
    
    def _files_are_identical(self, file1: Path, file2: Path) -> bool:
        """Check if two files are identical (same size and content)"""
        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False
            
            # Compare file content in chunks
            chunk_size = 8192
            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
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
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem use"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = sanitized.strip('. ')
        return sanitized or "unknown"

# Global instance
image_migration_service = ImageMigrationService()
