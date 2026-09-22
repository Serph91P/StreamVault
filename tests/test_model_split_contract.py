"""Regression contract for the first incremental ORM model-package slice."""

from __future__ import annotations

import ast
import importlib
import inspect as python_inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.database import Base, DatabaseLifecycle


EXPECTED_TABLES = {
    "active_recordings_state",
    "api_keys",
    "categories",
    "favorite_categories",
    "global_settings",
    "notification_settings",
    "notification_state",
    "proxy_settings",
    "push_subscriptions",
    "recording_processing_state",
    "recording_settings",
    "recordings",
    "refresh_tokens",
    "sessions",
    "stream_events",
    "stream_metadata",
    "streamer_recording_settings",
    "streamers",
    "streams",
    "system_config",
    "system_state",
    "twitch_upstream_coordination_state",
    "twitch_upstream_leases",
    "users",
}


def test_app_models_is_a_compatibility_package_with_category_reexports() -> None:
    models = importlib.import_module("app.models")
    category_models = importlib.import_module("app.models.categories")

    assert Path(models.__file__).name == "__init__.py"
    assert models.Category is category_models.Category
    assert models.FavoriteCategory is category_models.FavoriteCategory
    assert models.Category.__module__ == "app.models.categories"
    assert models.FavoriteCategory.__module__ == "app.models.categories"


def test_category_models_use_sqlalchemy_typed_mapping() -> None:
    category_models = importlib.import_module("app.models.categories")
    tree = ast.parse(python_inspect.getsource(category_models))
    model_classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in {"Category", "FavoriteCategory"}
    }

    assert set(model_classes) == {"Category", "FavoriteCategory"}
    for model_class in model_classes.values():
        annotated_fields = [
            node for node in model_class.body if isinstance(node, ast.AnnAssign)
        ]
        assert annotated_fields
        assert all(
            isinstance(field.annotation, ast.Subscript)
            and isinstance(field.annotation.value, ast.Name)
            and field.annotation.value.id == "Mapped"
            for field in annotated_fields
        )


def test_model_split_preserves_complete_metadata_and_category_table_contract() -> None:
    import app.models as models

    exported_tables = {
        getattr(models, model_name).__table__.name for model_name in models.__all__
    }
    assert exported_tables == EXPECTED_TABLES
    # Other feature-local models may share Base and be registered by earlier tests.
    assert EXPECTED_TABLES <= set(Base.metadata.tables)

    categories = Base.metadata.tables["categories"]
    favorites = Base.metadata.tables["favorite_categories"]

    assert list(categories.columns) == [
        categories.c.id,
        categories.c.twitch_id,
        categories.c.name,
        categories.c.box_art_url,
        categories.c.first_seen,
        categories.c.last_seen,
    ]
    assert categories.c.id.primary_key
    assert categories.c.id.autoincrement is True
    assert categories.c.twitch_id.unique is True
    assert categories.c.twitch_id.nullable is False
    assert categories.c.name.nullable is False
    assert categories.c.box_art_url.nullable is True
    assert categories.c.first_seen.server_default is not None
    assert categories.c.last_seen.server_default is not None
    assert categories.c.last_seen.onupdate is not None

    assert list(favorites.columns) == [
        favorites.c.id,
        favorites.c.user_id,
        favorites.c.category_id,
        favorites.c.created_at,
    ]
    assert {
        constraint.name
        for constraint in favorites.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    } == {"uq_user_category"}
    assert {foreign_key.target_fullname for foreign_key in favorites.foreign_keys} == {
        "categories.id",
        "users.id",
    }


def test_category_slice_round_trips_with_existing_user_relationships() -> None:
    from app.models import Category, FavoriteCategory, User

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, Category.__table__, FavoriteCategory.__table__],
    )

    with Session(engine) as session:
        user = User(username="model-split", password="not-a-real-secret")
        category = Category(twitch_id="509658", name="Just Chatting")
        favorite = FavoriteCategory(user=user, category=category)
        session.add(favorite)
        session.commit()
        session.refresh(favorite)

        assert favorite.user is user
        assert favorite.category is category
        assert user.favorite_categories == [favorite]
        assert category.favorites == [favorite]

    table_names = set(inspect(engine).get_table_names())
    assert table_names == {"categories", "favorite_categories", "users"}
    engine.dispose()


@pytest.mark.asyncio
async def test_category_vertical_slice_uses_async_session_and_explicit_transactions(
    tmp_path: Path,
) -> None:
    from app.models import Category, FavoriteCategory, User
    from app.services.categories.category_service import (
        CategoryRepository,
        CategoryService,
    )

    for method_name in (
        "list_all",
        "get_by_id",
        "favorite_ids_for_user",
        "get_favorite",
        "add_favorite",
        "remove_favorite",
        "list_favorites",
    ):
        assert python_inspect.iscoroutinefunction(
            getattr(CategoryRepository, method_name)
        )
    for method_name in (
        "list_categories",
        "add_favorite",
        "remove_favorite",
        "list_favorites",
    ):
        assert python_inspect.iscoroutinefunction(getattr(CategoryService, method_name))

    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'categories.db'}")
    Base.metadata.create_all(
        lifecycle.sync_engine,
        tables=[User.__table__, Category.__table__, FavoriteCategory.__table__],
    )
    with lifecycle.sync_session_factory() as sync_session:
        sync_session.add_all(
            [
                User(id=1, username="async-category", password="test-only"),
                Category(id=1, twitch_id="509658", name="Just Chatting"),
            ]
        )
        sync_session.commit()

    async with lifecycle.async_session_factory() as async_session:
        service = CategoryService(CategoryRepository(async_session))

        initial = await service.list_categories(1)
        assert initial["categories"][0]["is_favorite"] is False

        added = await service.add_favorite(1, 1)
        assert added["is_favorite"] is True

        favorites = await service.list_favorites(1)
        assert [item["id"] for item in favorites["categories"]] == [1]

        removed = await service.remove_favorite(1, 1)
        assert removed["is_favorite"] is False
        assert (await service.list_favorites(1)) == {"categories": []}

    with lifecycle.sync_session_factory() as sync_session:
        assert sync_session.query(FavoriteCategory).count() == 0

    await lifecycle.adispose()


def test_category_route_and_dependency_use_async_database_seam() -> None:
    from app import dependencies
    from app.routes import categories

    assert python_inspect.iscoroutinefunction(dependencies.get_category_service)
    route_source = python_inspect.getsource(categories)
    dependency_source = python_inspect.getsource(dependencies.get_category_service)
    assert "await category_service.list_categories" in route_source
    assert "await category_service.add_favorite" in route_source
    assert "await category_service.remove_favorite" in route_source
    assert "await category_service.list_favorites" in route_source
    assert "Depends(get_async_db)" in dependency_source


class _CategoryServiceRepository:
    """Small repository seam for exercising service transaction failures."""

    def __init__(self, category=None, favorite=None, commit_error=None) -> None:
        self.category = category
        self.favorite = favorite
        self.commit_error = commit_error
        self.rollback_calls = 0
        self.add_calls = 0
        self.remove_calls = 0

    async def get_by_id(self, category_id):
        return self.category

    async def get_favorite(self, user_id, category_id):
        return self.favorite

    async def add_favorite(self, user_id, category_id):
        self.add_calls += 1

    async def remove_favorite(self, favorite):
        self.remove_calls += 1

    async def commit(self):
        if self.commit_error:
            raise self.commit_error

    async def rollback(self):
        self.rollback_calls += 1


def _service_category():
    return SimpleNamespace(
        id=7,
        twitch_id="category-7",
        name="Contract Test",
        box_art_url=None,
        first_seen=None,
        last_seen=None,
    )


@pytest.mark.asyncio
async def test_category_service_missing_category_rolls_back_and_raises() -> None:
    from app.services.categories.category_service import CategoryService

    repository = _CategoryServiceRepository()
    service = CategoryService(repository)

    with pytest.raises(LookupError):
        await service.add_favorite(1, 7)
    with pytest.raises(LookupError):
        await service.remove_favorite(1, 7)

    assert repository.rollback_calls == 2
    assert repository.add_calls == 0
    assert repository.remove_calls == 0


@pytest.mark.asyncio
async def test_category_service_commit_failure_rolls_back_and_reraises() -> None:
    from app.services.categories.category_service import CategoryService

    error = RuntimeError("commit failed")
    repository = _CategoryServiceRepository(
        category=_service_category(), commit_error=error
    )
    service = CategoryService(repository)

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.add_favorite(1, 7)
    assert repository.add_calls == 1
    assert repository.rollback_calls == 1

    repository.favorite = SimpleNamespace(id=11)
    with pytest.raises(RuntimeError, match="commit failed"):
        await service.remove_favorite(1, 7)
    assert repository.remove_calls == 1
    assert repository.rollback_calls == 2
