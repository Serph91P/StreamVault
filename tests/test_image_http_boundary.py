"""Image transport is owned/bounded and filesystem I/O stays in drained workers."""

import importlib
from pathlib import Path
from threading import get_ident

import pytest
from aiohttp import web

from app.config.settings import Settings
from app.services.images.image_download_service import ImageDownloadService


@pytest.fixture
async def image_origin():
    import io
    import random
    from PIL import Image

    randomizer = random.Random(842)
    pixels = bytes(
        component
        for _ in range(128 * 128)
        for component in (
            randomizer.randrange(200, 256),
            randomizer.randrange(180),
            randomizer.randrange(190),
        )
    )
    buffer = io.BytesIO()
    Image.frombytes("RGB", (128, 128), pixels).save(buffer, "PNG")
    thumbnail_bytes = buffer.getvalue()
    seen = []

    async def serve(request):
        seen.append(
            (
                request.path,
                request.transport,
                request.headers.get("Cookie"),
                request.headers.get("User-Agent"),
            )
        )
        if request.path == "/redirect":
            raise web.HTTPFound("/image")
        if request.path == "/thumbnail":
            return web.Response(body=thumbnail_bytes, content_type="image/png")
        if request.path == "/denied":
            return web.Response(status=503)
        response = web.Response(body=b"fixture-image-bytes", content_type="image/jpeg")
        response.set_cookie("fixture", "not-replayed")
        return response

    app = web.Application()
    app.router.add_get("/{path}", serve)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    try:
        yield f"http://127.0.0.1:{runner.addresses[0][1]}", seen
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_image_transport_settings_and_pools_are_owned_and_closed_independently(
    tmp_path, image_origin
):
    base, seen = image_origin
    first = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test",
            RECORDING_DIRECTORY=str(tmp_path / "first"),
            _env_file=None,
        )
    )
    second = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test",
            RECORDING_DIRECTORY=str(tmp_path / "second"),
            _env_file=None,
        )
    )
    assert not (tmp_path / "first").exists() and not (tmp_path / "second").exists()
    try:
        a, b = (
            first.images_base_dir / "first.jpg",
            second.images_base_dir / "second.jpg",
        )
        assert await first.download_image(base + "/image", a)
        assert await first.download_image(base + "/image", a)
        assert await second.download_image(base + "/image", b)
        assert a.read_bytes() == b.read_bytes() == b"fixture-image-bytes"
        assert seen[0][1] is seen[1][1] and seen[2][1] is not seen[1][1]
        assert all(
            cookie is None and agent == "StreamVault" for _, _, cookie, agent in seen
        )
        assert await first.download_image(base + "/redirect", a)
        await first.close()
        assert await second.download_image(base + "/image", b)
        assert not await first.download_image(base + "/image", a)
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_image_destination_creation_and_file_lifetime_are_off_loop(
    tmp_path, image_origin, monkeypatch
):
    base, _ = image_origin
    service = ImageDownloadService()
    service.recordings_dir, service.images_base_dir = tmp_path, tmp_path / ".media"
    threads, opened, closed = [], [], []
    loop_thread = get_ident()
    original_mkdir, original_open = Path.mkdir, Path.open

    def mkdir(path, *args, **kwargs):
        if path.is_relative_to(tmp_path):
            threads.append(get_ident())
        return original_mkdir(path, *args, **kwargs)

    class Writer:
        def __init__(self, stream):
            self.stream = stream

        def write(self, data):
            threads.append(get_ident())
            return self.stream.write(data)

        def close(self):
            closed.append(get_ident())
            return self.stream.close()

    def open_file(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        if args and args[0] == "wb" and path.is_relative_to(tmp_path):
            opened.append(get_ident())
            return Writer(stream)
        return stream

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "open", open_file)
    try:
        target = service.images_base_dir / "nested" / "image.jpg"
        assert await service.download_image(base + "/image", target)
        assert target.read_bytes() == b"fixture-image-bytes"
        assert threads and loop_thread not in threads
        assert opened and closed and loop_thread not in opened + closed
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["artwork", "metadata", "head"])
async def test_existing_image_http_callers_use_the_managed_transport(
    tmp_path, image_origin, monkeypatch, consumer
):
    base, _ = image_origin
    service = ImageDownloadService()
    module = importlib.import_module("app.services.unified_image_service")
    facade = module.UnifiedImageService()
    facade.download_service = service
    monkeypatch.setattr(module, "unified_image_service", facade)
    target = tmp_path / (consumer + ".jpg")
    try:
        if consumer == "artwork":
            from app.services.media.artwork_service import ArtworkService

            assert await ArtworkService()._download_image(base + "/image", target)
            assert target.read_bytes() == b"fixture-image-bytes"
        elif consumer == "metadata":
            from app.services.media.metadata_service import MetadataService

            assert await MetadataService()._download_image(base + "/image", target)
            assert target.read_bytes() == b"fixture-image-bytes"
        else:
            from app.services.streamers.streamer_image_service import (
                StreamerImageService,
            )

            caller = StreamerImageService()
            caller.image_service = facade
            assert await caller.validate_image_url(base + "/image")
            assert not await caller.validate_image_url(base + "/redirect")
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_twitch_thumbnail_caller_consumes_real_image_and_persists_path(
    tmp_path, image_origin, monkeypatch
):
    from PIL import Image
    from app.database import Base, DatabaseLifecycle
    from app.models import Stream, Streamer, StreamMetadata

    thumbnail_module = importlib.import_module("app.services.media.thumbnail_service")
    base, _ = image_origin
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'thumbnail.db'}")
    service = ImageDownloadService()
    module = importlib.import_module("app.services.unified_image_service")
    facade = module.UnifiedImageService()
    facade.download_service = service
    monkeypatch.setattr(module, "unified_image_service", facade)
    monkeypatch.setattr(thumbnail_module, "SessionLocal", database.sync_session_factory)
    with database.sync_engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    with database.sync_session_factory() as session:
        session.add(Streamer(id=1, username="fixture", twitch_id="fixture"))
        session.flush()
        session.add(
            Stream(id=1, streamer_id=1, recording_path=str(tmp_path / "capture.mp4"))
        )
        session.commit()
    caller = thumbnail_module.ThumbnailService(
        session_factory=database.sync_session_factory
    )

    async def thumbnail_url(*args):
        return base + "/thumbnail"

    monkeypatch.setattr(caller, "get_stream_thumbnail", thumbnail_url)
    try:
        target = tmp_path / "capture-thumb.jpg"
        assert await caller.download_thumbnail(1, str(tmp_path)) == target
        with Image.open(target) as image:
            assert image.size == (128, 128)
        with database.sync_session_factory() as session:
            metadata = session.query(StreamMetadata).filter_by(stream_id=1).one()
            assert metadata.thumbnail_path == str(target)
            assert metadata.thumbnail_url == base + "/thumbnail"
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
async def test_injected_image_transport_is_borrowed_with_bounded_body_and_legacy_status_policy(
    tmp_path, image_origin
):
    from app.services.http_client import ManagedHTTPClient, HTTPPolicy

    base, _ = image_origin
    client = ManagedHTTPClient(HTTPPolicy(max_response_bytes=8))
    service = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        ),
        http_client=client,
    )
    try:
        target = service.images_base_dir / "image.jpg"
        assert not await service.download_image(base + "/denied", target)
        assert not service.is_download_failed(base + "/denied")
        assert not target.exists()
        assert not await service.download_image(base + "/image", target)
        assert service.is_download_failed(base + "/image")
        await service.close()
        # Closing a borrower must not close an explicitly supplied peer resource.
        assert (await client.request("HEAD", base + "/image")).status_code == 200
    finally:
        await service.close()
        await client.close()


@pytest.mark.asyncio
async def test_cancelled_file_open_is_drained_and_handle_closed(
    tmp_path, image_origin, monkeypatch
):
    import asyncio
    from threading import Event

    base, _ = image_origin
    service = ImageDownloadService(
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(tmp_path), _env_file=None
        )
    )
    entered, release = asyncio.Event(), Event()
    loop, opened = asyncio.get_running_loop(), []
    native_open = Path.open
    target = service.images_base_dir / "cancelled.jpg"

    def open_file(path, *args, **kwargs):
        stream = native_open(path, *args, **kwargs)
        if path == target and args and args[0] == "wb":
            opened.append(stream)
            loop.call_soon_threadsafe(entered.set)
            release.wait(5)
        return stream

    monkeypatch.setattr(Path, "open", open_file)
    operation = asyncio.create_task(service.download_image(base + "/image", target))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        operation.cancel()
        await asyncio.sleep(0.02)
        assert not operation.done() and not opened[0].closed
        operation.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(operation, 5)
        assert opened[0].closed
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await service.close()
