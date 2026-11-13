"""The compatibility image facade keeps each real catalogue and worker owner."""

import importlib
from threading import get_ident

import pytest

from app.config.settings import Settings
from app.models import Category, StreamMetadata, Streamer
from app.services.unified_image_service import UnifiedImageService
from tests import test_artwork_catalog_boundary

artwork_owners = test_artwork_catalog_boundary.artwork_owners
image_origin = test_artwork_catalog_boundary.image_origin


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["profile", "banner", "category", "artwork"])
async def test_unified_image_facade_uses_its_catalogue_for_every_delegate(
    artwork_owners, monkeypatch, kind
):
    existing, databases, queries, _, _, base = artwork_owners
    facades = []
    for service, database in zip(existing, databases, strict=True):
        with database.sync_session_factory() as session:
            session.add(Category(name="owner category", twitch_id="owner-category"))
            session.commit()
        facades.append(
            UnifiedImageService(
                settings=Settings(
                    ENVIRONMENT="test",
                    RECORDING_DIRECTORY=str(service.download_service.recordings_dir),
                    _env_file=None,
                ),
                session_factory=database.sync_session_factory,
            )
        )

    def forbidden_global_session():
        raise AssertionError("configuration-foreign catalogue")

    for module in (
        "profile_image_service",
        "banner_image_service",
        "category_image_service",
        "stream_artwork_service",
    ):
        monkeypatch.setattr(
            importlib.import_module("app.services.images." + module),
            "SessionLocal",
            forbidden_global_session,
        )
    loop_thread = get_ident()
    queries.clear()
    try:
        for index, facade in enumerate(facades):
            native_session = facade.download_service.get_session

            async def checked_session(native=native_session):
                assert all(
                    database.sync_engine.pool.checkedout() == 0
                    for database in databases
                )
                return await native()

            monkeypatch.setattr(facade.download_service, "get_session", checked_session)
            if kind == "profile":
                assert await facade.update_streamer_profile_image(1, base + "/image")
            elif kind == "banner":
                assert await facade.update_streamer_banner_image(1, base + "/image")
            elif kind == "category":
                assert await facade.update_category_image(
                    "owner category", base + "/image"
                )
            else:
                assert await facade.update_stream_artwork(1, base + "/image")
            assert queries and loop_thread not in queries
            queries.clear()
            with databases[index].sync_session_factory() as session:
                if kind == "profile":
                    assert (
                        session.query(Streamer)
                        .one()
                        .profile_image_url.startswith("/recordings/.media/profiles/")
                    )
                elif kind == "banner":
                    assert (
                        session.query(Streamer)
                        .one()
                        .offline_image_url.startswith("/data/images/banners/")
                    )
                elif kind == "category":
                    assert (
                        session.query(Category)
                        .one()
                        .box_art_url.startswith("/api/media/categories/")
                    )
                else:
                    assert (
                        session.query(StreamMetadata)
                        .one()
                        .thumbnail_url.startswith("/data/images/artwork/")
                    )
            queries.clear()
        assert (
            facades[0].download_service.session
            is not facades[1].download_service.session
        )
    finally:
        for facade in facades:
            await facade.close()


@pytest.mark.asyncio
async def test_missing_image_report_closes_scalar_source_before_worker_cache_reads(
    artwork_owners, monkeypatch
):
    existing, databases, queries, _, _, _ = artwork_owners
    database = databases[0]
    with database.sync_session_factory() as session:
        session.add(Category(name="missing category", twitch_id="missing-category"))
        session.commit()
    facade = UnifiedImageService(
        settings=Settings(
            ENVIRONMENT="test",
            RECORDING_DIRECTORY=str(existing[0].download_service.recordings_dir),
            _env_file=None,
        ),
        session_factory=database.sync_session_factory,
    )
    loop_thread = get_ident()
    native_cache = facade.get_cached_profile_image

    def checked_cache(streamer_id):
        assert get_ident() != loop_thread
        assert all(item.sync_engine.pool.checkedout() == 0 for item in databases)
        return native_cache(streamer_id)

    monkeypatch.setattr(facade, "get_cached_profile_image", checked_cache)
    queries.clear()
    try:
        assert await facade.get_missing_images_report() == {
            "missing_profiles": 1,
            "missing_categories": 1,
            "total_streamers": 1,
            "total_categories": 1,
        }
        assert queries and loop_thread not in queries
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await facade.close()
