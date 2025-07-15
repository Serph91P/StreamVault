"""
API routes for image management
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Streamer, Stream, Category
from app.services.unified_image_service import unified_image_service
from app.services.image_sync_service import image_sync_service

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/images",
    tags=["images-api"]
)

@router.get("/streamer/{streamer_id}")
async def get_streamer_image_info(streamer_id: int, db: Session = Depends(get_db)):
    """Get image information for a streamer"""
    try:
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail="Streamer not found")
            
        # Get cached image URL or fallback to original
        image_url = unified_image_service.get_profile_image_url(
            streamer_id, 
            streamer.profile_image_url
        )
        
        return {
            "streamer_id": streamer_id,
            "username": streamer.username,
            "image_url": image_url,
            "original_image_url": streamer.profile_image_url,
            "cached": str(streamer_id) in unified_image_service._profile_cache
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting streamer image info for {streamer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/streamer/{streamer_id}/download")
async def download_streamer_image(streamer_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Download and cache a streamer's profile image"""
    try:
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail="Streamer not found")
            
        if not streamer.profile_image_url:
            raise HTTPException(status_code=400, detail="No profile image URL available")
            
        # Add download task to background
        background_tasks.add_task(
            unified_image_service.download_profile_image,
            streamer_id,
            streamer.profile_image_url
        )
        
        return {"message": f"Profile image download started for {streamer.username}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting profile image download for {streamer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/category/{category_name}")
async def get_category_image_info(category_name: str):
    """Get image information for a category"""
    try:
        # Get cached image URL or fallback
        image_url = unified_image_service.get_category_image_url(category_name)
        
        return {
            "category_name": category_name,
            "image_url": image_url,
            "cached": category_name in unified_image_service._category_cache
        }
    except Exception as e:
        logger.error(f"Error getting category image info for {category_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/category/{category_name}/download")
async def download_category_image(category_name: str, background_tasks: BackgroundTasks):
    """Download and cache a category image"""
    try:
        # Add download task to background
        background_tasks.add_task(
            unified_image_service.download_category_image,
            category_name
        )
        
        return {"message": f"Category image download started for {category_name}"}
    except Exception as e:
        logger.error(f"Error starting category image download for {category_name}: {e}")
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

@router.post("/sync")
async def sync_all_images(background_tasks: BackgroundTasks):
    """Trigger sync of all images"""
    try:
        background_tasks.add_task(unified_image_service.sync_all_profile_images)
        background_tasks.add_task(unified_image_service.sync_all_category_images)
        return {"message": "Full image sync started"}
    except Exception as e:
        logger.error(f"Error starting full image sync: {e}")
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

@router.get("/streamers")
async def get_all_streamers_image_info(db: Session = Depends(get_db)):
    """Get image information for all streamers"""
    try:
        streamers = db.query(Streamer).all()
        
        result = []
        for streamer in streamers:
            image_url = unified_image_service.get_profile_image_url(
                streamer.id, 
                streamer.profile_image_url
            )
            
            result.append({
                "streamer_id": streamer.id,
                "username": streamer.username,
                "image_url": image_url,
                "original_image_url": streamer.profile_image_url,
                "cached": str(streamer.id) in unified_image_service._profile_cache
            })
            
        return result
    except Exception as e:
        logger.error(f"Error getting all streamers image info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/categories")
async def get_all_categories_image_info(db: Session = Depends(get_db)):
    """Get image information for all categories"""
    try:
        categories = db.query(Category).all()
        
        result = []
        for category in categories:
            image_url = unified_image_service.get_category_image_url(category.name)
            
            result.append({
                "category_name": category.name,
                "image_url": image_url,
                "cached": category.name in unified_image_service._category_cache
            })
            
        return result
    except Exception as e:
        logger.error(f"Error getting all categories image info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/sync/check-missing")
async def check_missing_images(background_tasks: BackgroundTasks):
    """Check for missing images and sync them"""
    try:
        background_tasks.add_task(image_sync_service.check_and_sync_missing_images)
        return {"message": "Missing images check started"}
    except Exception as e:
        logger.error(f"Error starting missing images check: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sync/queue-status")
async def get_sync_queue_status():
    """Get the current status of the image sync queue"""
    try:
        return {
            "queue_size": image_sync_service.get_queue_size(),
            "is_running": image_sync_service.is_running(),
            "service_initialized": unified_image_service._initialized
        }
    except Exception as e:
        logger.error(f"Error getting sync queue status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
