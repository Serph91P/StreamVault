"""Refresh missing images using closed, owner-local catalogue snapshots."""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Category, Stream, Streamer
from app.services.unified_image_service import (
    UnifiedImageService,
    unified_image_service,
)
from app.utils.async_db_utils import batch_process_items, run_in_thread_pool
from app.utils.file_utils import sanitize_filename

logger = logging.getLogger("streamvault")


class ImageRefreshService:
    """Service for checking and re-downloading missing images"""

    def __init__(
        self,
        *,
        image_service: UnifiedImageService | None = None,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._image_service = image_service
        self._session_factory = session_factory
        self.recordings_dir = (
            image_service.download_service.recordings_dir
            if image_service
            else Path("/recordings")
        )
        self.media_dir = self.recordings_dir / ".media"

    @property
    def _images(self) -> UnifiedImageService:
        return self._image_service or unified_image_service

    def _sessions(self) -> Session:
        return (self._session_factory or SessionLocal)()

    async def check_and_refresh_missing_images(self) -> dict[str, int]:
        """Check for missing images and re-download them"""
        profiles = await self._refresh_missing_profile_images()
        categories = await self._refresh_missing_category_images()
        artwork = await self._refresh_missing_stream_artwork()
        return {
            "profile_images_refreshed": profiles["refreshed"],
            "category_images_refreshed": categories["refreshed"],
            "stream_artwork_refreshed": artwork["refreshed"],
            "errors": profiles["errors"] + categories["errors"] + artwork["errors"],
        }

    def _profile_sources(self) -> list[tuple[int, str]]:
        sources = []
        with self._sessions() as session:
            for streamer in session.query(Streamer).all():
                paths = [
                    self.media_dir / "profiles" / name
                    for name in (
                        f"profile_avatar_{streamer.twitch_id}.jpg",
                        f"profile_avatar_{streamer.id}.jpg",
                        f"streamer_{streamer.id}.jpg",
                    )
                ]
                if any(path.exists() for path in paths):
                    continue
                source = streamer.profile_image_url
                if not source or not source.startswith("http"):
                    source = streamer.original_profile_image_url
                if not source or not source.startswith("http"):
                    twitch_id = streamer.twitch_id
                    source = (
                        f"https://static-cdn.jtvnw.net/jtv_user_pictures/{twitch_id}-profile_image-300x300.png"
                        if twitch_id
                        and twitch_id.replace("-", "").replace("_", "").isalnum()
                        else None
                    )
                if source:
                    sources.append((streamer.id, source))
        return sources

    async def _refresh_missing_profile_images(self) -> dict[str, int]:
        stats = {"refreshed": 0, "errors": 0}
        try:
            sources = await run_in_thread_pool(self._profile_sources)
            async for batch in batch_process_items(
                sources, batch_size=10, max_concurrent=3
            ):
                results = await asyncio.gather(
                    *(
                        self._download_profile_image(identity, source)
                        for identity, source in batch
                    ),
                    return_exceptions=True,
                )
                for result in results:
                    if isinstance(result, asyncio.CancelledError):
                        raise result
                    if isinstance(result, BaseException):
                        stats["errors"] += 1
                    elif result:
                        stats["refreshed"] += 1
                    else:
                        stats["errors"] += 1
        except Exception as error:
            logger.error("Error refreshing profile images (%s)", type(error).__name__)
            stats["errors"] += 1
        return stats

    def _publish_profile(self, streamer_id: int, cached_path: str) -> bool:
        with self._sessions() as session:
            streamer = session.get(Streamer, streamer_id)
            if streamer is None:
                return False
            streamer.profile_image_url = cached_path
            session.commit()
            return True

    async def _download_profile_image(self, streamer_id: int, source_url: str) -> bool:
        try:
            if not source_url.startswith("http"):
                return False
            path = await self._images.download_profile_image(streamer_id, source_url)
            return (
                await run_in_thread_pool(self._publish_profile, streamer_id, path)
                if path
                else False
            )
        except Exception as error:
            logger.error("Profile refresh failed (%s)", type(error).__name__)
            return False

    def _category_sources(self) -> list[tuple[str, str]]:
        with self._sessions() as session:
            return [
                (category.name, category.box_art_url)
                for category in session.query(Category).all()
                if category.box_art_url
                and category.box_art_url.startswith("http")
                and not (
                    self.media_dir
                    / "categories"
                    / f"{sanitize_filename(category.name)}.jpg"
                ).exists()
            ]

    def _publish_category(self, name: str, cached_path: str) -> bool:
        with self._sessions() as session:
            category = session.query(Category).filter(Category.name == name).first()
            if category is None:
                return False
            category.box_art_url = cached_path
            session.commit()
            return True

    async def _refresh_missing_category_images(self) -> dict[str, int]:
        stats = {"refreshed": 0, "errors": 0}
        try:
            sources = await run_in_thread_pool(self._category_sources)
            for name, source in sources:
                try:
                    path = await self._images.download_category_image(name, source)
                    published = False
                    if path:
                        published = await run_in_thread_pool(
                            self._publish_category, name, path
                        )
                    if published:
                        stats["refreshed"] += 1
                    else:
                        stats["errors"] += 1
                except Exception as error:
                    logger.error("Category refresh failed (%s)", type(error).__name__)
                    stats["errors"] += 1
        except Exception as error:
            logger.error("Error refreshing category images (%s)", type(error).__name__)
            stats["errors"] += 1
        return stats

    def _artwork_sources(self) -> list[tuple[int, int, str]]:
        with self._sessions() as session:
            result = []
            for stream in (
                session.query(Stream)
                .order_by(Stream.started_at.desc())
                .limit(100)
                .all()
            ):
                metadata = stream.stream_metadata
                path = (
                    self.media_dir
                    / "artwork"
                    / f"streamer_{stream.streamer_id}"
                    / f"stream_{stream.id}.jpg"
                )
                if not path.exists() and metadata and metadata.thumbnail_url:
                    result.append(
                        (stream.id, stream.streamer_id, metadata.thumbnail_url)
                    )
            return result

    async def _refresh_missing_stream_artwork(self) -> dict[str, int]:
        stats = {"refreshed": 0, "errors": 0}
        try:
            sources = await run_in_thread_pool(self._artwork_sources)
            async for batch in batch_process_items(
                sources, batch_size=5, max_concurrent=2
            ):
                results = await asyncio.gather(
                    *(self._download_stream_artwork(*source) for source in batch),
                    return_exceptions=True,
                )
                for result in results:
                    if isinstance(result, asyncio.CancelledError):
                        raise result
                    if isinstance(result, BaseException):
                        stats["errors"] += 1
                    elif result:
                        stats["refreshed"] += 1
                    else:
                        stats["errors"] += 1
        except Exception as error:
            logger.error("Error refreshing stream artwork (%s)", type(error).__name__)
            stats["errors"] += 1
        return stats

    async def _download_stream_artwork(
        self, stream_id: int, streamer_id: int, source: str
    ) -> bool:
        try:
            return bool(
                await self._images.download_stream_artwork(
                    stream_id, streamer_id, source
                )
            )
        except Exception as error:
            logger.error("Artwork refresh failed (%s)", type(error).__name__)
            return False

    def _specific_profile_source(self, streamer_id: int) -> str | None:
        with self._sessions() as session:
            streamer = session.get(Streamer, streamer_id)
            return streamer.profile_image_url if streamer else None

    async def refresh_specific_streamer(self, streamer_id: int) -> bool:
        """Refresh images for a specific streamer"""
        try:
            source = await run_in_thread_pool(
                self._specific_profile_source, streamer_id
            )
            if source and source.startswith("http"):
                return await self._download_profile_image(streamer_id, source)
        except Exception as error:
            logger.error("Error refreshing streamer images (%s)", type(error).__name__)
        return False

    def _specific_category_source(self, name: str) -> str | None:
        with self._sessions() as session:
            category = session.query(Category).filter(Category.name == name).first()
            return category.box_art_url if category else None

    async def refresh_specific_category(self, category_name: str) -> bool:
        """Refresh image for a specific category"""
        try:
            source = await run_in_thread_pool(
                self._specific_category_source, category_name
            )
            if source and source.startswith("http"):
                path = await self._images.download_category_image(category_name, source)
                return (
                    await run_in_thread_pool(
                        self._publish_category, category_name, path
                    )
                    if path
                    else False
                )
        except Exception as error:
            logger.error("Error refreshing category image (%s)", type(error).__name__)
        return False


image_refresh_service = ImageRefreshService()
