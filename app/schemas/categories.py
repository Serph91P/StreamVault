from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class CategoryBase(BaseModel):
    name: str
    twitch_id: str
    box_art_url: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_seen: datetime
    last_seen: datetime
    is_favorite: bool = False  # Wird vom Backend gefüllt


class CategoryList(BaseModel):
    categories: List[CategoryResponse]


class FavoriteCategoryCreate(BaseModel):
    category_id: int


class FavoriteCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category_id: int
    category: CategoryResponse
