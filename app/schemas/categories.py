from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CategoryBase(BaseModel):
    name: str
    twitch_id: str
    box_art_url: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    first_seen: datetime
    last_seen: datetime
    is_favorite: bool = False  # Wird vom Backend gefüllt

    class Config:
        from_attributes = True

class CategoryList(BaseModel):
    categories: List[CategoryResponse]

class FavoriteCategoryCreate(BaseModel):
    category_id: int

class FavoriteCategoryResponse(BaseModel):
    id: int
    user_id: int
    category_id: int
    category: CategoryResponse

    class Config:
        from_attributes = True
