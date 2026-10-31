"""Real HTTP, filesystem and disposable DB regressions for profile refreshes."""

import asyncio
from collections import Counter
from io import BytesIO
import socket

from aiohttp import web
from cachetools import TTLCache
from PIL import Image
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Streamer
from app.services.images import profile_image_service as profile_module
from app.services.images import auto_image_sync_service as auto_module
from app.services.images import image_sync_service as sync_module
from app.services.images.image_download_service import ImageDownloadService
from app.services.images.profile_image_service import ProfileImageService
from app.services.unified_image_service import UnifiedImageService


def jpeg(color):
    output = BytesIO()
    Image.new("RGB", (2, 2), color).save(output, format="JPEG")
    return output.getvalue()


@pytest_asyncio.fixture
async def origin():
    state = {
        "requests": Counter(),
        "mode": "ok",
        "started": asyncio.Event(),
        "release": asyncio.Event(),
        "a": jpeg("red"),
        "b": jpeg("blue"),
    }

    async def serve(request):
        name = request.match_info["name"]
        state["requests"][name] += 1
        if name == "b" and state["mode"] == "error":
            return web.Response(status=503)
        if name == "b" and state["mode"] == "text":
            return web.Response(text="not an image")
        if name == "b" and state["mode"] == "empty":
            return web.Response(body=b"", content_type="image/jpeg")
        if name == "b" and state["mode"] in ("partial", "blocked"):
            response = web.StreamResponse(
                headers={"Content-Type": "image/jpeg", "Content-Length": "1000000"}
            )
            await response.prepare(request)
            await response.write(state["b"] * 256)
            state["started"].set()
            if state["mode"] == "blocked":
                await state["release"].wait()
            request.transport.close()
            return response
        return web.Response(body=state[name], content_type="image/jpeg")

    app = web.Application()
    app.router.add_get("/{name}", serve)
    runner = web.AppRunner(app)
    await runner.setup()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    site = web.SockSite(runner, sock)
    await site.start()
    state["url"] = f"http://127.0.0.1:{sock.getsockname()[1]}"
    try:
        yield state
    finally:
        state["release"].set()
        await runner.cleanup()


@pytest_asyncio.fixture
async def profile(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'profiles.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Streamer(id=777, twitch_id="777", username="synthetic"))
        db.commit()
    monkeypatch.setattr(profile_module, "SessionLocal", sessions)
    monkeypatch.setattr("app.database.SessionLocal", sessions)
    monkeypatch.setattr(auto_module, "SessionLocal", sessions)
    downloader = ImageDownloadService()
    downloader._initialized = True
    downloader.images_base_dir = tmp_path / ".media"
    downloader.images_base_dir.mkdir()
    service = ProfileImageService(downloader)
    try:
        yield service, sessions
    finally:
        await service.close()
        engine.dispose()


def image_path(service):
    return service.profiles_dir / "profile_avatar_777.jpg"


async def test_changed_url_replaces_bytes_but_same_url_is_http_cache_hit(
    profile, origin
):
    service, _ = profile
    a, b = (origin["url"] + suffix for suffix in ("/a", "/b"))
    expected = "/recordings/.media/profiles/profile_avatar_777.jpg"
    assert await service.download_profile_image(777, a) == expected
    assert image_path(service).read_bytes() == origin["a"]
    assert await service.download_profile_image(777, a) == expected
    assert origin["requests"] == {"a": 1}
    assert await service.download_profile_image(777, b) == expected
    assert origin["requests"] == {"a": 1, "b": 1}
    assert image_path(service).read_bytes() == origin["b"]
    assert await service.download_profile_image(777, b) == expected
    assert origin["requests"] == {"a": 1, "b": 1}


@pytest.mark.parametrize("mode", ["error", "partial", "text", "empty"])
async def test_failed_refresh_preserves_old_image_mapping_and_allows_retry(
    profile, origin, mode
):
    service, _ = profile
    a, b = (origin["url"] + suffix for suffix in ("/a", "/b"))
    cached = await service.download_profile_image(777, a)
    origin["mode"] = mode
    assert await service.download_profile_image(777, b) is None
    assert image_path(service).read_bytes() == origin["a"]
    assert service.get_cached_profile_image(777) == cached
    assert await service.download_profile_image(777, a) == cached
    assert origin["requests"] == {"a": 1, "b": 1}
    assert list(service.profiles_dir.iterdir()) == [image_path(service)]
    origin["mode"] = "ok"
    assert await service.download_profile_image(777, b) == cached
    assert image_path(service).read_bytes() == origin["b"]
    assert origin["requests"] == {"a": 1, "b": 2}


async def test_cancelled_transfer_never_publishes_partial_image(profile, origin):
    service, _ = profile
    cached = await service.download_profile_image(777, origin["url"] + "/a")
    # Explicit invalidation also forces the baseline implementation into HTTP.
    service._profile_cache.clear()
    origin["mode"] = "blocked"
    task = asyncio.create_task(
        service.download_profile_image(777, origin["url"] + "/b")
    )
    try:
        await asyncio.wait_for(origin["started"].wait(), 3)

        # Wait for a real filesystem write, not merely server-side headers.
        async def written():
            while not any(
                p.stat().st_size > 0 and p.read_bytes() != origin["a"]
                for p in service.profiles_dir.rglob("*")
                if p.is_file()
            ):
                await asyncio.sleep(0.01)

        await asyncio.wait_for(written(), 3)
        assert image_path(service).read_bytes() == origin["a"]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        origin["release"].set()
    assert image_path(service).read_bytes() == origin["a"]
    assert list(service.profiles_dir.iterdir()) == [image_path(service)]
    origin["mode"] = "ok"
    assert await service.download_profile_image(777, origin["url"] + "/b") == cached
    assert image_path(service).read_bytes() == origin["b"]


async def test_reloaded_file_has_no_proven_source_identity(profile, origin):
    service, _ = profile
    cached = await service.download_profile_image(777, origin["url"] + "/a")
    reloaded = ProfileImageService(service.download_service)
    assert reloaded.get_cached_profile_image(777) == cached
    assert await reloaded.download_profile_image(777, origin["url"] + "/b") == cached
    assert origin["requests"] == {"a": 1, "b": 1}
    assert image_path(reloaded).read_bytes() == origin["b"]


async def test_expiry_and_invalidation_require_new_http_fetch(profile, origin):
    service, _ = profile
    clock = [0]
    service._profile_cache = TTLCache(maxsize=1, ttl=10, timer=lambda: clock[0])
    url = origin["url"] + "/a"
    await service.download_profile_image(777, url)
    clock[0] = 11
    await service.download_profile_image(777, url)
    service._profile_cache.pop("777")
    await service.download_profile_image(777, url)
    assert origin["requests"] == {"a": 3}


async def test_auto_sync_persists_path_only_after_successful_refresh(
    profile, origin, monkeypatch
):
    service, sessions = profile
    # Keep the real facade and both sync callers, replacing only their global instance.
    facade = UnifiedImageService()
    facade.profile_service = service
    monkeypatch.setattr(auto_module, "unified_image_service", facade)
    monkeypatch.setattr(sync_module, "unified_image_service", facade)
    auto = auto_module.AutoImageSyncService()
    request = {
        "type": "streamer_profile",
        "streamer_id": 777,
        "profile_image_url": origin["url"] + "/a",
    }
    await auto._process_sync_request(request)
    with sessions() as db:
        cached = db.get(Streamer, 777).profile_image_url
    assert cached == "/recordings/.media/profiles/profile_avatar_777.jpg"
    request["profile_image_url"] = origin["url"] + "/b"
    origin["mode"] = "partial"
    await auto._process_sync_request(request)
    with sessions() as db:
        assert db.get(Streamer, 777).profile_image_url == cached
    assert image_path(service).read_bytes() == origin["a"]
    origin["mode"] = "ok"
    await auto._process_sync_request(request)
    await sync_module.ImageSyncService()._process_sync_request(request)
    with sessions() as db:
        assert db.get(Streamer, 777).profile_image_url == cached
    assert image_path(service).read_bytes() == origin["b"]
    assert origin["requests"] == {"a": 1, "b": 2}


async def test_replace_failure_preserves_source_and_retries(
    profile, origin, monkeypatch
):
    service, _ = profile
    cached = await service.download_profile_image(777, origin["url"] + "/a")
    from pathlib import Path

    def fail_replace(self, target):
        raise OSError("controlled replacement failure")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_replace)
        assert await service.download_profile_image(777, origin["url"] + "/b") is None
    assert image_path(service).read_bytes() == origin["a"]
    assert service.get_cached_profile_image(777) == cached
    assert await service.download_profile_image(777, origin["url"] + "/a") == cached
    assert await service.download_profile_image(777, origin["url"] + "/b") == cached
    assert image_path(service).read_bytes() == origin["b"]
    assert origin["requests"] == {"a": 1, "b": 2}
    assert list(service.profiles_dir.iterdir()) == [image_path(service)]


async def test_missing_input_and_local_bulk_sync_do_not_download(profile, origin):
    service, sessions = profile
    assert await service.download_profile_image(777, "") is None
    assert await service.download_profile_image(999, origin["url"] + "/a") is None
    with sessions() as db:
        db.get(Streamer, 777).profile_image_url = "/custom/avatar.jpg"
        db.commit()
    assert await service.sync_all_profile_images() == {
        "downloaded": 0,
        "skipped": 1,
        "failed": 0,
    }
    assert not origin["requests"]
    with sessions() as db:
        assert db.get(Streamer, 777).profile_image_url == "/custom/avatar.jpg"


async def test_profile_retry_does_not_change_other_downloaders_failure_policy(
    profile, origin
):
    service, _ = profile
    url = origin["url"] + "/a"
    service.download_service.mark_download_failed(url)
    target = service.download_service.images_base_dir / "other.jpg"
    assert not await service.download_service.download_image(url, target)
    assert not target.exists()
    assert not origin["requests"]
    assert await service.download_profile_image(777, url)
    assert image_path(service).read_bytes() == origin["a"]
    assert origin["requests"] == {"a": 1}
