"""Image serving routes for the unified image service."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_image_service
from app.models import Streamer

logger = logging.getLogger("streamvault")
router = APIRouter(prefix="/data/images", tags=["images"])


@router.get("/profiles/{filename}")
def serve_profile_image(filename: str, image_service=Depends(get_image_service)):
    """Serve a cached profile image"""
    try:
        file_path = image_service.profiles_dir / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                file_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        raise HTTPException(status_code=404, detail="Profile image not found")
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Error serving profile image (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories/{filename}")
def serve_category_image(filename: str, image_service=Depends(get_image_service)):
    """Serve a cached category image"""
    try:
        file_path = image_service.categories_dir / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                file_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        raise HTTPException(status_code=404, detail="Category image not found")
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Error serving category image (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/artwork/{streamer_id}/{filename}")
def serve_artwork_image(
    streamer_id: str, filename: str, image_service=Depends(get_image_service)
):
    """Serve a cached artwork image"""
    try:
        file_path = image_service.artwork_dir / f"streamer_{streamer_id}" / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                file_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        raise HTTPException(status_code=404, detail="Artwork image not found")
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Error serving artwork (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
def get_image_stats(image_service=Depends(get_image_service)):
    """Get statistics about cached images"""
    try:
        return JSONResponse(content=image_service.get_stats())
    except Exception as error:
        logger.error("Error getting image stats (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync/profiles")
async def sync_profile_images(
    background_tasks: BackgroundTasks, image_service=Depends(get_image_service)
):
    """Trigger sync of all profile images"""
    try:
        background_tasks.add_task(image_service.sync_all_profile_images)
        return {"message": "Profile image sync started"}
    except Exception as error:
        logger.error("Error starting profile image sync (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync/categories")
async def sync_category_images(
    background_tasks: BackgroundTasks, image_service=Depends(get_image_service)
):
    """Trigger sync of all category images"""
    try:
        background_tasks.add_task(image_service.sync_all_category_images)
        return {"message": "Category image sync started"}
    except Exception as error:
        logger.error("Error starting category image sync (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cleanup")
async def cleanup_orphaned_images(
    background_tasks: BackgroundTasks, image_service=Depends(get_image_service)
):
    """Clean up orphaned images"""
    try:
        background_tasks.add_task(image_service.cleanup_orphaned_images)
        return {"message": "Image cleanup started"}
    except Exception as error:
        logger.error("Error starting image cleanup (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/profile/{streamer_id}")
def get_profile_image_url(
    streamer_id: int,
    db: Session = Depends(get_db),
    image_service=Depends(get_image_service),
):
    """Get the URL for a streamer's profile image"""
    try:
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail="Streamer not found")
        image_url = image_service.get_profile_image_url(
            streamer_id, streamer.profile_image_url
        )
        return {"image_url": image_url}
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Error getting profile image URL (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/category/{category_name}")
async def get_category_image_url(
    category_name: str, image_service=Depends(get_image_service)
):
    """Get the URL for a category image"""
    try:
        return {"image_url": await image_service.get_category_image_url(category_name)}
    except Exception as error:
        logger.error("Error getting category image URL (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Internal server error")
