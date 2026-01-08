"""
Migration API Routes

Provides endpoints for data migration tasks and image refresh.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict
import logging

from app.services.migration.image_migration_service import image_migration_service
from app.services.images.image_refresh_service import image_refresh_service

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

        return MigrationResponse(success=True, message="Image migration completed successfully", stats=stats)
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
            image_migration_service.old_images_dir.exists() or image_migration_service.old_artwork_dir.exists()
        )

        return {
            "migration_needed": old_dirs_exist,
            "old_images_dir_exists": image_migration_service.old_images_dir.exists(),
            "old_artwork_dir_exists": image_migration_service.old_artwork_dir.exists(),
            "recordings_dir": str(image_migration_service.recordings_dir),
        }
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")


@router.post("/images/refresh", response_model=MigrationResponse)
async def refresh_missing_images(background_tasks: BackgroundTasks):
    """
    Check for missing images and re-download them.

    This will:
    - Check for missing profile images and re-download them
    - Check for missing category images and re-download them
    - Check for missing stream artwork and re-download them
    - Update database with cached paths
    """
    try:
        # Run refresh in background
        stats = await image_refresh_service.check_and_refresh_missing_images()

        return MigrationResponse(success=True, message="Image refresh completed successfully", stats=stats)
    except Exception as e:
        logger.error(f"Error during image refresh: {e}")
        raise HTTPException(status_code=500, detail=f"Image refresh failed: {str(e)}")


@router.post("/images/refresh/streamer/{streamer_id}")
async def refresh_streamer_images(streamer_id: int):
    """
    Refresh images for a specific streamer
    """
    try:
        success = await image_refresh_service.refresh_specific_streamer(streamer_id)

        if success:
            return {"success": True, "message": f"Images refreshed for streamer {streamer_id}"}
        else:
            return {"success": False, "message": f"Failed to refresh images for streamer {streamer_id}"}

    except Exception as e:
        logger.error(f"Error refreshing streamer images: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh streamer images: {str(e)}")


@router.post("/images/refresh/category/{category_name}")
async def refresh_category_image(category_name: str):
    """
    Refresh image for a specific category
    """
    try:
        success = await image_refresh_service.refresh_specific_category(category_name)

        if success:
            return {"success": True, "message": f"Image refreshed for category {category_name}"}
        else:
            return {"success": False, "message": f"Failed to refresh image for category {category_name}"}

    except Exception as e:
        logger.error(f"Error refreshing category image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh category image: {str(e)}")
