"""Banner callers must retain the downloader's actual image Content-Type guard."""

import pytest
from aiohttp import web

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Streamer
from app.services.images.banner_image_service import BannerImageService
from app.services.images.image_download_service import ImageDownloadService


@pytest.mark.asyncio
async def test_banner_rejects_html_before_file_and_catalogue_publication(tmp_path):
    async def html(_request):
        return web.Response(
            text="<html>upstream login</html>", content_type="text/html"
        )

    origin = web.Application()
    origin.router.add_get("/image", html)
    runner = web.AppRunner(origin)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'banner.db'}")
    downloader = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        )
    )
    service = BannerImageService(
        downloader, session_factory=database.sync_session_factory
    )
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(
                Streamer(
                    id=1,
                    twitch_id="fixture",
                    username="fixture",
                    offline_image_url="old-image",
                )
            )
            session.commit()
        url = f"http://127.0.0.1:{runner.addresses[0][1]}/image"
        assert await service.download_banner_image(1, url) is None
        assert not (tmp_path / ".media/banners/banner_1.jpg").exists()
        assert service._banner_cache.get(1) is None
        with database.sync_session_factory() as session:
            assert session.get(Streamer, 1).offline_image_url == "old-image"
    finally:
        await downloader.close()
        await database.adispose()
        await runner.cleanup()
