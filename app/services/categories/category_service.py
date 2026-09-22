"""Async category persistence and service boundary.

The category slice is the first request path moved to ``AsyncSession`` under the
DB-I/O ADR. Repositories only query, add, delete, and flush. The service owns the
commit/rollback boundary so route handlers never manage transactions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, FavoriteCategory


class CategoryRepository:
    """Async data access for ``Category`` and ``FavoriteCategory`` rows."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_all(self) -> Sequence[Category]:
        result = await self._db.execute(select(Category).order_by(Category.name))
        return result.scalars().all()

    async def get_by_id(self, category_id: int) -> Category | None:
        result = await self._db.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def favorite_ids_for_user(self, user_id: int) -> set[int]:
        result = await self._db.execute(
            select(FavoriteCategory.category_id).where(
                FavoriteCategory.user_id == user_id
            )
        )
        return {
            category_id for category_id in result.scalars() if category_id is not None
        }

    async def get_favorite(
        self, user_id: int, category_id: int
    ) -> FavoriteCategory | None:
        result = await self._db.execute(
            select(FavoriteCategory).where(
                FavoriteCategory.user_id == user_id,
                FavoriteCategory.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_favorite(self, user_id: int, category_id: int) -> None:
        self._db.add(FavoriteCategory(user_id=user_id, category_id=category_id))
        await self._db.flush()

    async def remove_favorite(self, favorite: FavoriteCategory) -> None:
        await self._db.delete(favorite)
        await self._db.flush()

    async def list_favorites(self, user_id: int) -> Sequence[Category]:
        result = await self._db.execute(
            select(Category)
            .join(FavoriteCategory)
            .where(FavoriteCategory.user_id == user_id)
            .order_by(Category.name)
        )
        return result.scalars().all()

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()


class CategoryService:
    """Category operations returning the existing frontend-compatible payloads."""

    def __init__(self, repository: CategoryRepository) -> None:
        self._repo = repository

    @staticmethod
    def _category_dict(category: Category, is_favorite: bool) -> dict[str, Any]:
        return {
            "id": category.id,
            "twitch_id": category.twitch_id,
            "name": category.name,
            "box_art_url": category.box_art_url,
            "first_seen": category.first_seen,
            "last_seen": category.last_seen,
            "is_favorite": is_favorite,
        }

    async def list_categories(self, user_id: int) -> dict[str, Any]:
        categories = await self._repo.list_all()
        favorite_ids = await self._repo.favorite_ids_for_user(user_id)
        return {
            "categories": [
                self._category_dict(category, category.id in favorite_ids)
                for category in categories
            ]
        }

    async def add_favorite(self, user_id: int, category_id: int) -> dict[str, Any]:
        try:
            category = await self._repo.get_by_id(category_id)
            if not category:
                raise LookupError(category_id)
            if not await self._repo.get_favorite(user_id, category_id):
                await self._repo.add_favorite(user_id, category_id)
            await self._repo.commit()
            return self._category_dict(category, True)
        except Exception:
            await self._repo.rollback()
            raise

    async def remove_favorite(self, user_id: int, category_id: int) -> dict[str, Any]:
        try:
            category = await self._repo.get_by_id(category_id)
            if not category:
                raise LookupError(category_id)
            favorite = await self._repo.get_favorite(user_id, category_id)
            if favorite:
                await self._repo.remove_favorite(favorite)
            await self._repo.commit()
            return self._category_dict(category, False)
        except Exception:
            await self._repo.rollback()
            raise

    async def list_favorites(self, user_id: int) -> dict[str, Any]:
        favorites = await self._repo.list_favorites(user_id)
        return {
            "categories": [
                self._category_dict(category, True) for category in favorites
            ]
        }
