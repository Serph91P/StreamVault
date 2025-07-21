"""
Migration API Routes

Provides endpoints for data migration tasks.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict
import logging

from app.services.migration.image_migration_service import image_migration_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/migration", tags=["migration"])

class MigrationResponse(BaseModel):
    """Response model for migration operations"""
    success: bool
    message: str
    stats: Dict[str, int]

@router.post("/images", response_model=MigrationResponse)
async def migrate_images(background_tasks: BackgroundTasks):
    """
    Migrate images from old directory structure to new simplified structure.
    
    This will:
    - Move images from .images/ and .artwork/ to streamer directories
    - Remove duplicates
    - Clean up empty old directories
    """
    try:
        # Run migration in background
        stats = await image_migration_service.migrate_all_images()
        
        return MigrationResponse(
            success=True,
            message="Image migration completed successfully",
            stats=stats
        )
    except Exception as e:
        logger.error(f"Error during image migration: {e}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

@router.get("/images/status")
async def get_migration_status():
    """
    Check if migration is needed by looking for old directory structures
    """
    try:
        old_dirs_exist = (
            image_migration_service.old_images_dir.exists() or 
            image_migration_service.old_artwork_dir.exists()
        )
        
        return {
            "migration_needed": old_dirs_exist,
            "old_images_dir_exists": image_migration_service.old_images_dir.exists(),
            "old_artwork_dir_exists": image_migration_service.old_artwork_dir.exists(),
            "recordings_dir": str(image_migration_service.recordings_dir)
        }
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")
