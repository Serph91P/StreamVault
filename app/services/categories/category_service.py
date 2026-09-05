"""
CategoryService - focused domain seam for the categories router.

Extracts the reusable category/favorite database workflow out of
``app.routes.categories`` (Phase 4A, issue #826). The router now depends on a
``CategoryService`` via DI instead of running ad-hoc sync SQL directly.

The repository talks to a sync ``Session`` (matching the existing
``StreamerRepository`` style). Writes commit on the caller-owned session, the
same behaviour as the original router.
"""

import logging

from sqlalchemy.orm import Session

from app.models import Category, FavoriteCategory

logger = logging.getLogger("streamvault")


class CategoryRepository:
    """Sync data access for ``Category`` and ``FavoriteCategory`` rows."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self):
        return self._db.query(Category).order_by(Category.name).all()

    def get_by_id(self, category_id: int):
        return self._db.query(Category).filter(Category.id == category_id).first()

    def favorite_ids_for_user(self, user_id: int) -> set:
        return {
            category_id
            for (category_id,) in self._db.query(FavoriteCategory.category_id)
            .filter(FavoriteCategory.user_id == user_id)
            .all()
        }

    def get_favorite(self, user_id: int, category_id: int):
        return (
            self._db.query(FavoriteCategory)
            .filter(
                FavoriteCategory.user_id == user_id,
                FavoriteCategory.category_id == category_id,
            )
            .first()
        )

    def add_favorite(self, user_id: int, category_id: int) -> None:
        self._db.add(FavoriteCategory(user_id=user_id, category_id=category_id))
        self._db.commit()

    def remove_favorite(self, favorite) -> None:
        self._db.delete(favorite)
        self._db.commit()

    def list_favorites(self, user_id: int):
        return (
            self._db.query(Category)
            .join(FavoriteCategory)
            .filter(FavoriteCategory.user_id == user_id)
            .order_by(Category.name)
            .all()
        )


class CategoryService:
    """High-level category operations returning frontend-compatible dicts."""

    def __init__(self, repository: CategoryRepository) -> None:
        self._repo = repository

    @staticmethod
    def _category_dict(category, is_favorite: bool) -> dict:
        return {
            "id": category.id,
            "twitch_id": category.twitch_id,
            "name": category.name,
            "box_art_url": category.box_art_url,
            "first_seen": category.first_seen,
            "last_seen": category.last_seen,
            "is_favorite": is_favorite,
        }

    def list_categories(self, user_id: int) -> dict:
        categories = self._repo.list_all()
        favorite_ids = self._repo.favorite_ids_for_user(user_id)
        return {
            "categories": [
                self._category_dict(category, category.id in favorite_ids)
                for category in categories
            ]
        }

    def add_favorite(self, user_id: int, category_id: int) -> dict:
        category = self._repo.get_by_id(category_id)
        if not category:
            raise LookupError(category_id)
        if not self._repo.get_favorite(user_id, category_id):
            self._repo.add_favorite(user_id, category_id)
        return self._category_dict(category, True)

    def remove_favorite(self, user_id: int, category_id: int) -> dict:
        category = self._repo.get_by_id(category_id)
        if not category:
            raise LookupError(category_id)
        favorite = self._repo.get_favorite(user_id, category_id)
        if favorite:
            self._repo.remove_favorite(favorite)
        return self._category_dict(category, False)

    def list_favorites(self, user_id: int) -> dict:
        favorites = self._repo.list_favorites(user_id)
        return {
            "categories": [
                self._category_dict(category, True) for category in favorites
            ]
        }
