"""
StreamArtworkService - Stream artwork/thumbnail management

Extracted from unified_image_service.py God Class
Handles downloading, caching, and serving of stream artwork and thumbnails.
"""

import logging
from collections.abc import Callable
from app.utils.async_db_utils import run_in_thread_pool
from pathlib import Path
from typing import Dict, Optional, List, TypedDict
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Stream, StreamMetadata
from .image_download_service import ImageDownloadService

logger = logging.getLogger("streamvault")


class ArtworkSource(TypedDict, total=False):
    stream_id: int
    streamer_id: int
    thumbnail_url: str


class StreamArtworkService:
    """Handles stream artwork and thumbnail management"""

    def __init__(
        self,
        download_service: Optional[ImageDownloadService] = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ):
        self._session_factory = session_factory
        self.download_service = download_service or ImageDownloadService()
        self.artwork_dir: Path | None = None

    def _ensure_artwork_dir(self) -> Path:
        """Ensure artwork directory exists"""
        if self.artwork_dir is None:
            directory = self.download_service._resolve_destination_path(
                self.download_service.get_images_base_dir() / "artwork"
            )
            directory.mkdir(parents=True, exist_ok=True)
            self.artwork_dir = directory
        return self.artwork_dir

    def _get_streamer_artwork_dir(self, streamer_id: int) -> Path:
        """Get artwork directory for a specific streamer"""
        root = self._ensure_artwork_dir()
        streamer_dir = self.download_service._resolve_destination_path(
            root / f"streamer_{streamer_id}"
        )
        streamer_dir.mkdir(parents=True, exist_ok=True)
        return streamer_dir

    def _prepare_artwork_path(
        self, stream_id: int, streamer_id: int
    ) -> tuple[Path, bool]:
        directory = self._get_streamer_artwork_dir(streamer_id)
        path = self.download_service._resolve_destination_path(
            directory / f"stream_{stream_id}.jpg"
        )
        return path, path.exists()

    async def download_stream_artwork(
        self, stream_id: int, streamer_id: int, thumbnail_url: str
    ) -> Optional[str]:
        """
        Download and cache stream artwork/thumbnail

        Args:
            stream_id: ID of the stream
            streamer_id: ID of the streamer
            thumbnail_url: URL of the thumbnail image

        Returns:
            Relative path to the cached image or None if failed
        """
        if not thumbnail_url:
            return None

        # Skip if previously failed
        if self.download_service.is_download_failed(thumbnail_url):
            return None

        try:
            file_path, exists = await run_in_thread_pool(
                self._prepare_artwork_path, stream_id, streamer_id
            )
            filename = file_path.name
            if exists:
                return f"/data/images/artwork/streamer_{streamer_id}/{filename}"

            success = await self.download_service.download_image(
                thumbnail_url, file_path
            )
            if success:
                relative_path = (
                    f"/data/images/artwork/streamer_{streamer_id}/{filename}"
                )
                logger.info(
                    f"Successfully cached stream artwork for stream {stream_id}"
                )
                return relative_path
            else:
                logger.warning(
                    f"Failed to download stream artwork for stream {stream_id}"
                )
                self.download_service.mark_download_failed(thumbnail_url)
                return None

        except Exception as e:
            logger.error(
                f"Error downloading stream artwork for stream {stream_id}: {e}"
            )
            self.download_service.mark_download_failed(thumbnail_url)
            return None

    def get_cached_stream_artwork(
        self, stream_id: int, streamer_id: int
    ) -> Optional[str]:
        """Get cached stream artwork path"""
        file_path, exists = self._prepare_artwork_path(stream_id, streamer_id)
        if exists:
            return f"/data/images/artwork/streamer_{streamer_id}/{file_path.name}"
        return None

    def _stream_owner(self, stream_id: int) -> int | None:
        with (self._session_factory or SessionLocal)() as db:
            owner = db.query(Stream.streamer_id).filter(Stream.id == stream_id).scalar()
            return owner if isinstance(owner, int) else None

    def _persist_artwork(self, updates: list[tuple[int, str]]) -> set[int]:
        with (self._session_factory or SessionLocal)() as db:
            changed: set[int] = set()
            for stream_id, path in updates:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    continue
                if not stream.stream_metadata:
                    metadata = StreamMetadata(stream_id=stream_id)
                    db.add(metadata)
                    stream.stream_metadata = metadata
                stream.stream_metadata.thumbnail_url = path
                changed.add(stream_id)
            db.commit()
            return changed

    async def update_stream_artwork(self, stream_id: int, thumbnail_url: str) -> bool:
        """Close the owner snapshot before HTTP and persist in a separate worker."""
        try:
            owner = await run_in_thread_pool(self._stream_owner, stream_id)
            if owner is None:
                return False
            cached = await self.download_stream_artwork(stream_id, owner, thumbnail_url)
            if cached:
                changed = await run_in_thread_pool(
                    self._persist_artwork, [(stream_id, cached)]
                )
                return stream_id in changed
        except Exception as error:
            logger.error("Stream artwork update failed: %s", type(error).__name__)
        return False

    def _artwork_sources(
        self, stream_ids: list[int] | None
    ) -> list[tuple[int, int | None, str | None]]:
        with (self._session_factory or SessionLocal)() as db:
            query = db.query(
                Stream.id, Stream.streamer_id, StreamMetadata.thumbnail_url
            ).outerjoin(StreamMetadata, StreamMetadata.stream_id == Stream.id)
            if stream_ids:
                query = query.filter(Stream.id.in_(stream_ids))
            return [(row.id, row.streamer_id, row.thumbnail_url) for row in query.all()]

    async def sync_stream_artwork(
        self, stream_ids: List[int] | None = None
    ) -> Dict[str, int]:
        """Keep only scalar snapshots while awaiting upstream downloads."""
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        updates: list[tuple[int, str]] = []
        try:
            sources = await run_in_thread_pool(self._artwork_sources, stream_ids)
            for stream_id, owner, source in sources:
                if source and source.startswith("http"):
                    cached = (
                        await self.download_stream_artwork(stream_id, owner, source)
                        if owner is not None
                        else None
                    )
                    if cached:
                        updates.append((stream_id, cached))
                    else:
                        stats["failed"] += 1
                else:
                    stats["skipped"] += 1
            changed = await run_in_thread_pool(self._persist_artwork, updates)
            stats["downloaded"] = len(changed)
            stats["failed"] += len(updates) - len(changed)
        except Exception as error:
            stats["failed"] += len(updates)
            logger.error("Stream artwork sync failed: %s", type(error).__name__)
        logger.info("Stream artwork sync completed: %s", stats)
        return stats

    async def bulk_download_artwork(
        self, artwork_data: List[ArtworkSource]
    ) -> Dict[str, int]:
        """Bulk download stream artwork from provided data"""
        stats = {"downloaded": 0, "failed": 0}

        for artwork_info in artwork_data:
            stream_id = artwork_info.get("stream_id")
            streamer_id = artwork_info.get("streamer_id")
            thumbnail_url = artwork_info.get("thumbnail_url")

            if not stream_id or not streamer_id or not thumbnail_url:
                continue

            cached_path = await self.download_stream_artwork(
                stream_id, streamer_id, thumbnail_url
            )
            if cached_path:
                stats["downloaded"] += 1
            else:
                stats["failed"] += 1

        logger.info(f"Bulk artwork download completed: {stats}")
        return stats

    def get_artwork_cache_stats(self) -> Dict[str, int]:
        """Get statistics about artwork cache"""
        try:
            root = self._ensure_artwork_dir()

            total_files = 0
            streamer_count = 0

            for streamer_dir in root.glob("streamer_*"):
                self.download_service._resolve_destination_path(streamer_dir)
                if streamer_dir.is_dir():
                    streamer_count += 1
                    total_files += len(list(streamer_dir.glob("*.jpg")))

            return {
                "cached_artworks": total_files,
                "streamers_with_artwork": streamer_count,
                "failed_downloads": len(
                    [
                        url
                        for url in self.download_service._failed_downloads
                        if "thumbnail" in url or "artwork" in url
                    ]
                ),
            }
        except Exception as e:
            logger.error(f"Error getting artwork cache stats: {e}")
            return {
                "cached_artworks": 0,
                "streamers_with_artwork": 0,
                "failed_downloads": 0,
            }

    async def cleanup_old_artwork(self, days_old: int = 30) -> int:
        return await run_in_thread_pool(self._cleanup_old_artwork, days_old)

    def _cleanup_old_artwork(self, days_old: int) -> int:
        """Remove artwork files older than specified days"""
        from datetime import datetime, timedelta

        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)

        try:
            root = self._ensure_artwork_dir()

            for streamer_dir in root.glob("streamer_*"):
                self.download_service._resolve_destination_path(streamer_dir)
                if streamer_dir.is_dir():
                    for artwork_file in streamer_dir.glob("*.jpg"):
                        try:
                            # Check file modification time
                            file_time = datetime.fromtimestamp(
                                artwork_file.stat().st_mtime
                            )
                            if file_time < cutoff_date:
                                artwork_file.unlink()
                                cleaned_count += 1
                                logger.debug(f"Removed old artwork: {artwork_file}")
                        except Exception as e:
                            logger.error(
                                f"Error checking/removing artwork file {artwork_file}: {e}"
                            )

                    # Remove empty directories
                    try:
                        if not any(streamer_dir.iterdir()):
                            streamer_dir.rmdir()
                            logger.debug(
                                f"Removed empty artwork directory: {streamer_dir}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error removing empty directory {streamer_dir}: {e}"
                        )

        except Exception as e:
            logger.error(f"Error during artwork cleanup: {e}")

        logger.info(f"Cleaned up {cleaned_count} old artwork files")
        return cleaned_count

    async def cleanup_unused_artwork(self) -> int:
        return await run_in_thread_pool(self._cleanup_unused_artwork)

    def _cleanup_unused_artwork(self) -> int:
        """Remove artwork that is no longer associated with any stream"""
        cleaned_count = 0

        try:
            root = self._ensure_artwork_dir()

            # Get all stream IDs from database
            with (self._session_factory or SessionLocal)() as db:
                active_stream_ids = set(str(s.id) for s in db.query(Stream.id).all())

            for streamer_dir in root.glob("streamer_*"):
                self.download_service._resolve_destination_path(streamer_dir)
                if streamer_dir.is_dir():
                    for artwork_file in streamer_dir.glob("stream_*.jpg"):
                        try:
                            stream_id = artwork_file.stem.replace("stream_", "")

                            if stream_id not in active_stream_ids:
                                artwork_file.unlink()
                                cleaned_count += 1
                                logger.debug(
                                    f"Removed unused artwork: {artwork_file.name}"
                                )
                        except Exception as e:
                            logger.error(
                                f"Error removing artwork file {artwork_file}: {e}"
                            )

        except Exception as e:
            logger.error(f"Error during artwork cleanup: {e}")

        logger.info(f"Cleaned up {cleaned_count} unused artwork files")
        return cleaned_count

    async def close(self) -> None:
        """Close the download service"""
        await self.download_service.close()
