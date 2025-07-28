from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category, FavoriteCategory, User
from app.schemas.categories import CategoryResponse, CategoryList, FavoriteCategoryCreate
from app.dependencies import get_current_user
from app.services.unified_image_service import unified_image_service
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("", response_model=CategoryList)
async def get_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all categories with favorite status"""
    # Ändere die Abfrage, um alle Kategorien einzuschließen, auch solche ohne Streams
    categories = db.query(Category).order_by(Category.name).all()
    
    # Debug-Ausgabe hinzufügen
    logger.debug(f"Found {len(categories)} categories in database")
    for category in categories:
        logger.debug(f"Category: {category.name}, ID: {category.id}, twitch_id: {category.twitch_id}")
    
    # Favoriten für aktuellen Benutzer finden
    favorite_category_ids = {
        category_id for (category_id,) in 
        db.query(FavoriteCategory.category_id)
        .filter(FavoriteCategory.user_id == current_user.id)
        .all()
    }
    
    # Kategorien mit Favoriten-Status zurückgeben
    result = []
    for category in categories:
        cat_dict = {
            "id": category.id,
            "twitch_id": category.twitch_id,
            "name": category.name,
            "box_art_url": category.box_art_url,
            "first_seen": category.first_seen,
            "last_seen": category.last_seen,
            "is_favorite": category.id in favorite_category_ids
        }
        result.append(cat_dict)
    
    return {"categories": result}
@router.post("/favorites", response_model=CategoryResponse)
async def add_favorite_category(
    data: FavoriteCategoryCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Mark a category as favorite"""
    # Check if the category exists
    category = db.query(Category).filter(Category.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if favorite already exists
    existing_favorite = db.query(FavoriteCategory).filter(
        FavoriteCategory.user_id == current_user.id,
        FavoriteCategory.category_id == data.category_id
    ).first()
    
    if not existing_favorite:
        # Create new favorite
        new_favorite = FavoriteCategory(
            user_id=current_user.id,
            category_id=data.category_id
        )
        db.add(new_favorite)
        db.commit()
    
    # Return category with favorite status
    return {
        "id": category.id,
        "twitch_id": category.twitch_id,
        "name": category.name,
        "box_art_url": category.box_art_url,
        "first_seen": category.first_seen,
        "last_seen": category.last_seen,
        "is_favorite": True
    }

@router.delete("/favorites/{category_id}", response_model=CategoryResponse)
async def remove_favorite_category(
    category_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Remove a category from favorites"""
    # Check if the category exists
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Find and delete favorite
    favorite = db.query(FavoriteCategory).filter(
        FavoriteCategory.user_id == current_user.id,
        FavoriteCategory.category_id == category_id
    ).first()
    
    if favorite:
        db.delete(favorite)
        db.commit()
    
    # Return category with updated favorite status
    return {
        "id": category.id,
        "twitch_id": category.twitch_id,
        "name": category.name,
        "box_art_url": category.box_art_url,
        "first_seen": category.first_seen,
        "last_seen": category.last_seen,
        "is_favorite": False
    }

@router.get("/favorites", response_model=CategoryList)
async def get_favorite_categories(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get all categories marked as favorites"""
    favorites = db.query(Category).join(FavoriteCategory).filter(
        FavoriteCategory.user_id == current_user.id
    ).order_by(Category.name).all()
    
    return {"categories": [
        {
            "id": category.id,
            "twitch_id": category.twitch_id,
            "name": category.name,
            "box_art_url": category.box_art_url,
            "first_seen": category.first_seen,
            "last_seen": category.last_seen,
            "is_favorite": True
        } for category in favorites
    ]}

# Category Image Management Endpoints

@router.get("/image/{category_name}")
async def get_category_image(category_name: str):
    """Get the URL for a category image - downloads immediately if not cached"""
    try:
        # First check if already cached
        cached_url = unified_image_service.get_cached_category_image(category_name)
        if cached_url:
            return {"category_name": category_name, "image_url": cached_url}
        
        # Not cached, try to download it immediately
        downloaded_url = await unified_image_service.download_category_image(category_name)
        if downloaded_url:
            return {"category_name": category_name, "image_url": downloaded_url}
        
        # Download failed, return None for icon fallback
        return {"category_name": category_name, "image_url": None}
    except Exception as e:
        logger.error(f"Error getting category image for {category_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category image")

@router.post("/images/batch")
async def get_multiple_category_images(category_names: List[str]):
    """Get URLs for multiple category images in a single request to reduce load"""
    try:
        results = {}
        for category_name in category_names:
            try:
                image_url = unified_image_service.get_category_image_url(category_name)
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
    category_names: List[str]
):
    """Preload category images in the background"""
    try:
        # Start the preloading in the background
        for category_name in category_names:
            background_tasks.add_task(unified_image_service.download_category_image, category_name)
        
        return {
            "message": f"Started preloading {len(category_names)} category images",
            "categories": category_names
        }
    except Exception as e:
        logger.error(f"Error preloading category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to start preloading")

@router.post("/refresh-images")
async def refresh_category_images(
    background_tasks: BackgroundTasks,
    category_names: List[str] = Body(...)
):
    """Refresh/re-download category images even if they exist"""
    try:
        # Start the refresh in the background
        # Use unified image service for category refresh
        for category_name in category_names:
            background_tasks.add_task(unified_image_service.download_category_image, category_name)
        
        return {
            "message": f"Started refreshing {len(category_names)} category images",
            "categories": category_names
        }
    except Exception as e:
        logger.error(f"Error refreshing category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to start refresh")

@router.post("/cleanup-images")
async def cleanup_old_images(days_old: int = 30):
    """Clean up old cached category images"""
    try:
        # Use unified image service for cleanup
        await unified_image_service.cleanup_orphaned_images()
        return {"message": f"Cleaned up category images older than {days_old} days"}
    except Exception as e:
        logger.error(f"Error cleaning up category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup images")

@router.get("/cache-status")
async def get_cache_status():
    """Get information about the category image cache"""
    try:
        stats = unified_image_service.get_stats()
        cache_info = {
            "cached_categories": stats.get("categories_cached", 0),
            "failed_downloads": stats.get("failed_downloads", 0),
            "cache_directory": stats.get("storage_path", ""),
            "cached_categories_list": list(unified_image_service._category_cache.keys())
        }
        return cache_info
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache status")

@router.get("/missing-images")
async def get_missing_images_report():
    """Get a report of categories that are missing images"""
    try:
        # Use unified image service for detailed missing images report
        report = await unified_image_service.get_missing_images_report()
        
        if "error" in report:
            raise HTTPException(status_code=500, detail="An internal error occurred while generating the missing images report")
        return report
    except Exception as e:
        logger.error(f"Error getting missing images report: {e}")
        raise HTTPException(status_code=500, detail="Failed to get missing images report")
