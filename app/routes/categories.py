from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category, FavoriteCategory, User
from app.schemas.categories import CategoryResponse, CategoryList, FavoriteCategoryCreate
from app.dependencies import get_current_user
from app.services.category_image_service import category_image_service
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
    """Get the URL for a category image"""
    try:
        image_url = category_image_service.get_category_image_url(category_name)
        return {"category_name": category_name, "image_url": image_url}
    except Exception as e:
        logger.error(f"Error getting category image for {category_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category image")

@router.post("/preload-images")
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

@router.post("/cleanup-images")
async def cleanup_old_images(days_old: int = 30):
    """Clean up old cached category images"""
    try:
        category_image_service.cleanup_old_images(days_old)
        return {"message": f"Cleaned up category images older than {days_old} days"}
    except Exception as e:
        logger.error(f"Error cleaning up category images: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup images")

@router.get("/cache-status")
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
