"""
API endpoints for category image management
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
from ..services.category_image_service import category_image_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("/image/{category_name}")
async def get_category_image(category_name: str):
    """Get the URL for a category image"""
    try:
        image_url = category_image_service.get_category_image_url(category_name)
        return {"category_name": category_name, "image_url": image_url}
    except Exception as e:
        logger.error(f"Error getting category image for {category_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category image")

@router.post("/preload")
async def preload_category_images(
    background_tasks: BackgroundTasks,
    category_names: List[str]
):
    """Preload category images in the background"""
    try:
        # Start the preloading in the background
        background_tasks.add_task(category_image_service.preload_categories, category_names)
        
        return {
            "message": f"Started preloading {len(category_names)} category images",
            "categories": category_names
        }
    except Exception as e:
        logger.error(f"Error preloading category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to start preloading")

@router.post("/cleanup")
async def cleanup_old_images(days_old: int = 30):
    """Clean up old cached category images"""
    try:
        category_image_service.cleanup_old_images(days_old)
        return {"message": f"Cleaned up category images older than {days_old} days"}
    except Exception as e:
        logger.error(f"Error cleaning up category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup images")

@router.get("/cache/status")
async def get_cache_status():
    """Get information about the category image cache"""
    try:
        cache_info = {
            "cached_categories": len(category_image_service._category_cache),
            "failed_downloads": len(category_image_service._failed_downloads),
            "cache_directory": str(category_image_service.images_dir),
            "cached_categories_list": list(category_image_service._category_cache.keys())
        }
        return cache_info
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache status")
