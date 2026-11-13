"""Image endpoints must close SQL scopes before awaitable image lookups."""

import asyncio
import importlib
from threading import get_ident

import pytest

from app.services.unified_image_service import UnifiedImageService
from tests import test_category_catalog_boundary

category_owners = test_category_catalog_boundary.category_owners
image_origin = test_category_catalog_boundary.image_origin


@pytest.mark.asyncio
async def test_all_category_image_info_projects_names_before_await(
    category_owners,
):
    services, databases, queries, _, checkouts, base = category_owners
    service, database = services[0], databases[0]
    facade = UnifiedImageService()
    facade.category_service = service
    facade._category_cache = service._category_cache
    module = importlib.import_module("app.routes.api_images")

    queries.clear()
    with database.sync_session_factory() as session:
        result = await module.get_all_categories_image_info(session, facade)
        assert database.sync_engine.pool.checkedout() == 0
    await asyncio.gather(*tuple(service._background_tasks))
    assert result[0]["category_name"] == "Just Chatting"
    assert result[0]["image_url"] == base + "/image"
    assert queries and get_ident() not in queries
    assert checkouts and all(
        count == 0 for observation in checkouts for count in observation
    )


@pytest.mark.asyncio
async def test_category_image_route_offloads_legacy_cache_lookup(category_owners):
    services, _, queries, _, checkouts, _ = category_owners
    service = services[0]
    facade = UnifiedImageService()
    facade.category_service = service
    facade._category_cache = service._category_cache
    module = importlib.import_module("app.routes.categories")
    queries.clear()
    result = await module.get_category_image("Just Chatting", facade)
    assert result == {
        "category_name": "Just Chatting",
        "image_url": "/api/media/categories/just_chatting.jpg",
    }
    assert queries and get_ident() not in queries
    assert checkouts and all(
        count == 0 for observation in checkouts for count in observation
    )
