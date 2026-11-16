"""Artwork failure outcomes retain retries, identities and on-disk bytes."""

import builtins
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest

from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer
from app.services.media.artwork_service import ArtworkService
from app.utils.async_db_utils import run_in_thread_pool
from aiohttp import web


@pytest.fixture
async def image_origin():
    async def rejected(request):
        if request.path == "/html":
            return web.Response(text="not an image", content_type="text/html")
        return web.Response(status=503 if request.path == "/failure" else 404)

    app = web.Application()
    app.router.add_get("/{path}", rejected)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    try:
        yield f"http://127.0.0.1:{runner.addresses[0][1]}"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["season-write", "metadata-dir", "catalog"])
async def test_artwork_metadata_failure_returns_false_and_can_retry(
    tmp_path, monkeypatch, fault
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'artwork.db'}")
    service = ArtworkService(
        recordings_dir=tmp_path / "media", session_factory=database.sync_session_factory
    )
    try:
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as db:
            streamer = Streamer(id=1, username="alice", twitch_id="alice")
            db.add(streamer)
            db.flush()
            db.add(
                Stream(
                    streamer_id=1, started_at=datetime(2026, 11, 1, tzinfo=timezone.utc)
                )
            )
            db.commit()
        native_open, native_mkdir = builtins.open, Path.mkdir
        attempts = []

        def opened(path, *args, **kwargs):
            if str(path).endswith("/season.nfo"):
                attempts.append(get_ident())
                raise PermissionError("synthetic denied season output")
            return native_open(path, *args, **kwargs)

        def mkdir(path, *args, **kwargs):
            if path == service.media_base_path / "metadata" / "alice":
                attempts.append(get_ident())
                raise PermissionError("synthetic denied metadata directory")
            return native_mkdir(path, *args, **kwargs)

        def sessions():
            attempts.append(get_ident())
            raise OSError("synthetic unavailable catalogue")

        with monkeypatch.context() as patch:
            if fault == "season-write":
                patch.setattr(builtins, "open", opened)
            elif fault == "metadata-dir":
                patch.setattr(Path, "mkdir", mkdir)
            else:
                patch.setattr(service, "_session_factory", sessions)
            assert await service.save_streamer_metadata(streamer) is False
        assert attempts and get_ident() not in attempts
        assert database.sync_engine.pool.checkedout() == 0
        assert await service.save_streamer_metadata(streamer)
        assert (
            service.media_base_path / "metadata/alice/Season_2026-11/season.nfo"
        ).is_file()
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
async def test_artwork_missing_or_transient_identities_never_publish(tmp_path):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'artwork.db'}")
    service = ArtworkService(
        recordings_dir=tmp_path / "media", session_factory=database.sync_session_factory
    )
    try:
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        assert (
            await service.save_streamer_metadata(
                Streamer(username="transient", twitch_id="transient")
            )
            is False
        )
        assert (
            await service.save_streamer_artwork(
                Streamer(username="transient", twitch_id="transient")
            )
            is False
        )
        assert await service._save_artwork_by_id(777) is False
        assert await run_in_thread_pool(service._save_metadata_by_id, 777) is False
        assert service._streamer_identity(object()) is None
        assert not service.media_base_path.exists()
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/html", "/failure", "/missing"])
async def test_standalone_artwork_rejects_nonimage_or_failed_http(
    tmp_path, image_origin, path
):
    base = image_origin
    service = ArtworkService(recordings_dir=tmp_path)
    destination = tmp_path / "avatar.jpg"
    try:
        assert await service._download_image(base + path, destination) is False
        assert not destination.exists()
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_standalone_artwork_missing_local_source_is_not_downloaded(tmp_path):
    service = ArtworkService(recordings_dir=tmp_path)
    assert (
        await service._download_image(
            str(tmp_path / "absent.jpg"), tmp_path / "out.jpg"
        )
        is False
    )
    assert not (tmp_path / "out.jpg").exists()
