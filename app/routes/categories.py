from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from typing import List
from app.models import User
from app.schemas.categories import (
    CategoryResponse,
    CategoryList,
    FavoriteCategoryCreate,
)
from app.dependencies import (
    get_current_user,
    get_category_service,
    get_image_service,
)
from app.services.categories.category_service import CategoryService
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/categories", tags=["categories"])
MAX_CATEGORY_IMAGE_BATCH_SIZE = 200


def _require_bounded_image_batch(category_names: List[str]) -> None:
    """Reject oversized image fan-out instead of silently discarding entries."""
    if len(category_names) > MAX_CATEGORY_IMAGE_BATCH_SIZE:
        raise HTTPException(
            status_code=422,
            detail=(
                "A maximum of "
                f"{MAX_CATEGORY_IMAGE_BATCH_SIZE} category names is allowed per request"
            ),
        )


@router.get("", response_model=CategoryList)
async def get_categories(
    category_service: CategoryService = Depends(get_category_service),
    current_user: User = Depends(get_current_user),
):
    """Get all categories with favorite status"""
    # Bounded list validation: only clamp when the caller opts in; the legacy
    # no-parameter behaviour (return all categories) is preserved exactly.
    result = category_service.list_categories(current_user.id)
    logger.debug(
        f"Found {len(result['categories'])} categories in database (favorites resolved)"
    )
    return result


@router.post("/favorites", response_model=CategoryResponse)
async def add_favorite_category(
    data: FavoriteCategoryCreate,
    category_service: CategoryService = Depends(get_category_service),
    current_user: User = Depends(get_current_user),
):
    """Mark a category as favorite"""
    try:
        return category_service.add_favorite(current_user.id, data.category_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Category not found")


@router.delete("/favorites/{category_id}", response_model=CategoryResponse)
async def remove_favorite_category(
    category_id: int,
    category_service: CategoryService = Depends(get_category_service),
    current_user: User = Depends(get_current_user),
):
    """Remove a category from favorites"""
    try:
        return category_service.remove_favorite(current_user.id, category_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Category not found")


@router.get("/favorites", response_model=CategoryList)
async def get_favorite_categories(
    category_service: CategoryService = Depends(get_category_service),
    current_user: User = Depends(get_current_user),
):
    """Get all categories marked as favorites"""
    return category_service.list_favorites(current_user.id)


# Category Image Management Endpoints


@router.get("/image/{category_name}")
async def get_category_image(
    category_name: str, image_service=Depends(get_image_service)
):
    """Get the URL for a category image - downloads immediately if not cached"""
    try:
        # First check if already cached
        cached_url = image_service.get_cached_category_image(category_name)
        if cached_url:
            return {"category_name": category_name, "image_url": cached_url}

        # Not cached, try to download it immediately
        downloaded_url = await image_service.download_category_image(category_name)
        if downloaded_url:
            return {"category_name": category_name, "image_url": downloaded_url}

        # Download failed, return None for icon fallback
        return {"category_name": category_name, "image_url": None}
    except Exception as e:
        logger.error(f"Error getting category image for {category_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category image")


@router.post("/images/batch")
async def get_multiple_category_images(
    category_names: List[str], image_service=Depends(get_image_service)
):
    """Get URLs for multiple category images in a single request to reduce load"""
    _require_bounded_image_batch(category_names)
    try:
        results = {}
        for category_name in category_names:
            try:
                image_url = image_service.get_category_image_url(category_name)
                results[category_name] = image_url
            except Exception as e:
                logger.warning(f"Failed to get image for {category_name}: {e}")
                results[category_name] = None

        return {"category_images": results}
    except Exception as e:
        logger.error(f"Error getting batch category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category images")


@router.post("/preload-images")
async def preload_category_images(
    background_tasks: BackgroundTasks,
    category_names: List[str],
    image_service=Depends(get_image_service),
):
    """Preload category images in the background"""
    _require_bounded_image_batch(category_names)
    try:
        # Start the preloading in the background
        for category_name in category_names:
            background_tasks.add_task(
                image_service.download_category_image, category_name
            )

        return {
            "message": f"Started preloading {len(category_names)} category images",
            "categories": category_names,
        }
    except Exception as e:
        logger.error(f"Error preloading category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to start preloading")


@router.post("/refresh-images")
async def refresh_category_images(
    background_tasks: BackgroundTasks,
    category_names: List[str] = Body(...),
    image_service=Depends(get_image_service),
):
    """Refresh/re-download category images even if they exist"""
    _require_bounded_image_batch(category_names)
    try:
        # Start the refresh in the background
        # Use unified image service for category refresh
        for category_name in category_names:
            background_tasks.add_task(
                image_service.download_category_image, category_name
            )

        return {
            "message": f"Started refreshing {len(category_names)} category images",
            "categories": category_names,
        }
    except Exception as e:
        logger.error(f"Error refreshing category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to start refresh")


@router.post("/cleanup-images")
async def cleanup_old_images(
    days_old: int = 30, image_service=Depends(get_image_service)
):
    """Clean up old cached category images"""
    try:
        # Use unified image service for cleanup
        await image_service.cleanup_orphaned_images()
        return {"message": f"Cleaned up category images older than {days_old} days"}
    except Exception as e:
        logger.error(f"Error cleaning up category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup images")


@router.get("/cache-status")
async def get_cache_status(image_service=Depends(get_image_service)):
    """Get information about the category image cache"""
    try:
        stats = image_service.get_stats()
        cache_info = {
            "cached_categories": stats.get("categories_cached", 0),
            "failed_downloads": stats.get("failed_downloads", 0),
            "cache_directory": stats.get("storage_path", ""),
            "cached_categories_list": list(image_service._category_cache.keys()),
        }
        return cache_info
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache status")


@router.get("/missing-images")
async def get_missing_images_report(image_service=Depends(get_image_service)):
    """Get a report of categories that are missing images"""
    try:
        # Use unified image service for detailed missing images report
        report = await image_service.get_missing_images_report()

        if "error" in report:
            raise HTTPException(
                status_code=500,
                detail="An internal error occurred while generating the missing images report",
            )
        return report
    except Exception as e:
        logger.error(f"Error getting missing images report: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get missing images report"
        )
