"""
Image serving routes for the unified image service
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import logging

from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/data/images", tags=["images"])


@router.get("/profiles/{filename}")
async def serve_profile_image(filename: str):
    """Serve a cached profile image"""
    try:
        file_path = unified_image_service.profiles_dir / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                file_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},  # Cache for 1 day
            )
        else:
            raise HTTPException(status_code=404, detail="Profile image not found")
    except Exception as e:
        logger.error(f"Error serving profile image {filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories/{filename}")
async def serve_category_image(filename: str):
    """Serve a cached category image"""
    try:
        file_path = unified_image_service.categories_dir / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                file_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},  # Cache for 1 day
            )
        else:
            raise HTTPException(status_code=404, detail="Category image not found")
    except Exception as e:
        logger.error(f"Error serving category image {filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/artwork/{streamer_id}/{filename}")
async def serve_artwork_image(streamer_id: str, filename: str):
    """Serve a cached artwork image"""
    try:
        file_path = unified_image_service.artwork_dir / f"streamer_{streamer_id}" / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                file_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},  # Cache for 1 day
            )
        else:
            raise HTTPException(status_code=404, detail="Artwork image not found")
    except Exception as e:
        logger.error(f"Error serving artwork image {streamer_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_image_stats():
    """Get statistics about cached images"""
    try:
        stats = unified_image_service.get_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Error getting image stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync/profiles")
async def sync_profile_images(background_tasks: BackgroundTasks):
    """Trigger sync of all profile images"""
    try:
        background_tasks.add_task(unified_image_service.sync_all_profile_images)
        return {"message": "Profile image sync started"}
    except Exception as e:
        logger.error(f"Error starting profile image sync: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync/categories")
async def sync_category_images(background_tasks: BackgroundTasks):
    """Trigger sync of all category images"""
    try:
        background_tasks.add_task(unified_image_service.sync_all_category_images)
        return {"message": "Category image sync started"}
    except Exception as e:
        logger.error(f"Error starting category image sync: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cleanup")
async def cleanup_orphaned_images(background_tasks: BackgroundTasks):
    """Clean up orphaned images"""
    try:
        background_tasks.add_task(unified_image_service.cleanup_orphaned_images)
        return {"message": "Image cleanup started"}
    except Exception as e:
        logger.error(f"Error starting image cleanup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/profile/{streamer_id}")
async def get_profile_image_url(streamer_id: int):
    """Get the URL for a streamer's profile image"""
    try:
        # Get the cached URL or fallback
        from app.database import SessionLocal
        from app.models import Streamer

        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if not streamer:
                raise HTTPException(status_code=404, detail="Streamer not found")

            # Get cached image URL or fallback to original
            image_url = unified_image_service.get_profile_image_url(streamer_id, streamer.profile_image_url)

            return {"image_url": image_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile image URL for streamer {streamer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/category/{category_name}")
async def get_category_image_url(category_name: str):
    """Get the URL for a category image"""
    try:
        # Get the cached URL or fallback
        image_url = unified_image_service.get_category_image_url(category_name)
        return {"image_url": image_url}
    except Exception as e:
        logger.error(f"Error getting category image URL for {category_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
