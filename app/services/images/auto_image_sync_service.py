"""Automatic image sync with owner-local workers and closed catalogue pages."""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.constants import ASYNC_DELAYS
from app.database import SessionLocal
from app.models import Category, Streamer
from app.services.images.image_sync_service import SyncRequest
from app.services.unified_image_service import (
    UnifiedImageService,
    unified_image_service,
)
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


class AutoImageSyncService:
    """Service for automatically syncing images when entities are created/updated"""

    TWITCH_PROFILE_URL_TEMPLATE = "https://static-cdn.jtvnw.net/jtv_user_pictures/{twitch_id}-profile_image-300x300.png"

    def __init__(
        self,
        *,
        image_service: UnifiedImageService | None = None,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._image_service = image_service
        self._session_factory = session_factory
        self._sync_queue: asyncio.Queue[SyncRequest] = asyncio.Queue()
        self._sync_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def _images(self) -> UnifiedImageService:
        return self._image_service or unified_image_service

    @property
    def PROFILES_BASE_PATH(self) -> str:
        return (
            str(self._images.download_service.recordings_dir / ".media" / "profiles")
            + "/"
        )

    def _sessions(self) -> Session:
        return (self._session_factory or SessionLocal)()

    async def start_sync_worker(self):
        if self._sync_task is None or self._sync_task.done():
            self._running = True
            self._sync_task = asyncio.create_task(
                self._sync_worker(), name="streamvault:auto-image-sync"
            )

    async def stop_sync_worker(self):
        self._running = False
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    async def _sync_worker(self):
        while self._running:
            try:
                request = await asyncio.wait_for(self._sync_queue.get(), timeout=5.0)
                try:
                    await self._process_sync_request(request)
                finally:
                    self._sync_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error("Auto image worker failed (%s)", type(error).__name__)
                await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_WORKER_ERROR_WAIT)

    async def _process_sync_request(self, request: SyncRequest):
        try:
            request_type = request.get("type")
            if request_type == "streamer_profile":
                await self._sync_streamer_profile(request)
            elif request_type == "category_image":
                await self._sync_category_image(request)
            elif request_type == "stream_artwork":
                await self._sync_stream_artwork(request)
            else:
                logger.warning("Unknown auto image request type")
        except Exception as error:
            logger.error("Auto image request failed (%s)", type(error).__name__)

    def _publish_profile(self, streamer_id: int, cached_path: str) -> None:
        with self._sessions() as session:
            streamer = session.get(Streamer, streamer_id)
            if streamer is not None:
                streamer.profile_image_url = cached_path
                session.commit()

    async def _sync_streamer_profile(self, request: SyncRequest):
        identity, source = request.get("streamer_id"), request.get("profile_image_url")
        if identity and source:
            path = await self._images.download_profile_image(identity, source)
            if path:
                await run_in_thread_pool(self._publish_profile, identity, path)

    def _category_source(self, name: str) -> str | None:
        with self._sessions() as session:
            category = session.query(Category).filter(Category.name == name).first()
            return category.box_art_url if category else None

    def _publish_category(self, name: str, cached_path: str) -> None:
        with self._sessions() as session:
            category = session.query(Category).filter(Category.name == name).first()
            if category is not None:
                category.box_art_url = cached_path
                session.commit()

    async def _sync_category_image(self, request: SyncRequest):
        name, source = request.get("category_name"), request.get("image_url")
        if name:
            if not source:
                source = await run_in_thread_pool(self._category_source, name)
            if source and source.startswith("http"):
                path = await self._images.download_category_image(name, source)
                if path:
                    await run_in_thread_pool(self._publish_category, name, path)

    async def _sync_stream_artwork(self, request: SyncRequest):
        identity, owner, source = (
            request.get("stream_id"),
            request.get("streamer_id"),
            request.get("artwork_url"),
        )
        if identity and owner and source:
            await self._images.download_stream_artwork(identity, owner, source)

    async def request_streamer_profile_sync(
        self, streamer_id: int, profile_image_url: str
    ):
        await self._sync_queue.put(
            {
                "type": "streamer_profile",
                "streamer_id": streamer_id,
                "profile_image_url": profile_image_url,
            }
        )

    async def request_category_image_sync(
        self, category_name: str, image_url: str | None = None
    ):
        await self._sync_queue.put(
            {
                "type": "category_image",
                "category_name": category_name,
                "image_url": image_url,
            }
        )

    async def request_stream_artwork_sync(
        self, stream_id: int, streamer_id: int, artwork_url: str
    ):
        await self._sync_queue.put(
            {
                "type": "stream_artwork",
                "stream_id": stream_id,
                "streamer_id": streamer_id,
                "artwork_url": artwork_url,
            }
        )

    def _profile_page(
        self, limit: int, offset: int
    ) -> tuple[int, list[tuple[int, str]]]:
        with self._sessions() as session:
            streamers = session.query(Streamer).limit(limit).offset(offset).all()
            sources = []
            for streamer in streamers:
                source = streamer.profile_image_url
                if source and source.startswith("http"):
                    sources.append((streamer.id, source))
                elif source and source.startswith("/data/images/"):
                    if not (Path(self.PROFILES_BASE_PATH) / Path(source).name).exists():
                        sources.append(
                            (
                                streamer.id,
                                self.TWITCH_PROFILE_URL_TEMPLATE.format(
                                    twitch_id=streamer.twitch_id
                                ),
                            )
                        )
            return len(streamers), sources

    async def _queue_profile_page(self, limit: int, offset: int) -> tuple[int, int]:
        scanned, sources = await run_in_thread_pool(self._profile_page, limit, offset)
        for identity, source in sources:
            await self.request_streamer_profile_sync(identity, source)
        return scanned, len(sources)

    async def sync_all_existing_streamers(self, limit: int = 100, offset: int = 0):
        try:
            _, queued = await self._queue_profile_page(limit, offset)
            return queued
        except Exception as error:
            logger.error("Auto profile scan failed (%s)", type(error).__name__)
            return 0

    def _category_page(self, limit: int, offset: int) -> list[tuple[str, str]]:
        with self._sessions() as session:
            return [
                (row.name, row.box_art_url)
                for row in session.query(Category.name, Category.box_art_url)
                .filter(Category.box_art_url.ilike("http%"))
                .limit(limit)
                .offset(offset)
                .all()
            ]

    async def sync_all_existing_categories(self, limit: int = 100, offset: int = 0):
        try:
            sources = await run_in_thread_pool(self._category_page, limit, offset)
            for name, source in sources:
                await self.request_category_image_sync(name, source)
            return len(sources)
        except Exception as error:
            logger.error("Auto category scan failed (%s)", type(error).__name__)
            return 0

    async def sync_all_streamers_paginated(self, batch_size: int = 100):
        total_synced, offset = 0, 0
        while True:
            try:
                scanned, queued = await self._queue_profile_page(batch_size, offset)
            except Exception as error:
                logger.error("Auto profile page failed (%s)", type(error).__name__)
                return total_synced
            total_synced += queued
            if scanned < batch_size:
                break
            offset += batch_size
            await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_BATCH_DELAY)
        return total_synced

    async def sync_all_categories_paginated(self, batch_size: int = 100):
        total_synced, offset = 0, 0
        while True:
            count = await self.sync_all_existing_categories(
                limit=batch_size, offset=offset
            )
            total_synced += count
            if count < batch_size:
                break
            offset += batch_size
            await asyncio.sleep(ASYNC_DELAYS.IMAGE_SYNC_BATCH_DELAY)
        return total_synced

    def get_queue_size(self) -> int:
        return self._sync_queue.qsize()

    def is_running(self) -> bool:
        return (
            self._running and self._sync_task is not None and not self._sync_task.done()
        )


auto_image_sync_service = AutoImageSyncService()
