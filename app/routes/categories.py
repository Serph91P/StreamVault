from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category, FavoriteCategory, User
from app.schemas.categories import CategoryResponse, CategoryList, FavoriteCategoryCreate
from app.middleware.auth import get_current_user
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("", response_model=CategoryList)
async def get_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Alle Kategorien mit Favoriten-Status abrufen"""
    categories = db.query(Category).order_by(Category.name).all()
    
    # Favoriten für den aktuellen Benutzer finden
    favorite_category_ids = set(
        db.query(FavoriteCategory.category_id)
        .filter(FavoriteCategory.user_id == current_user.id)
        .all()
    )
    
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
    """Eine Kategorie als Favorit markieren"""
    # Prüfen, ob die Kategorie existiert
    category = db.query(Category).filter(Category.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Prüfen, ob bereits ein Favorit existiert
    existing_favorite = db.query(FavoriteCategory).filter(
        FavoriteCategory.user_id == current_user.id,
        FavoriteCategory.category_id == data.category_id
    ).first()
    
    if existing_favorite:
        # Bereits als Favorit markiert - nichts tun
        pass
    else:
        # Neuen Favoriten erstellen
        new_favorite = FavoriteCategory(
            user_id=current_user.id,
            category_id=data.category_id
        )
        db.add(new_favorite)
        db.commit()
    
    # Kategorie mit Favoriten-Status zurückgeben
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
    """Eine Kategorie als Favorit entfernen"""
    # Prüfen, ob die Kategorie existiert
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Favorit finden und löschen
    favorite = db.query(FavoriteCategory).filter(
        FavoriteCategory.user_id == current_user.id,
        FavoriteCategory.category_id == category_id
    ).first()
    
    if favorite:
        db.delete(favorite)
        db.commit()
    
    # Kategorie mit aktualisiertem Favoriten-Status zurückgeben
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
    """Alle als Favorit markierten Kategorien abrufen"""
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
