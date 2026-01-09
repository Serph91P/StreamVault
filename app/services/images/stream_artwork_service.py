"""
StreamArtworkService - Stream artwork/thumbnail management

Extracted from unified_image_service.py God Class
Handles downloading, caching, and serving of stream artwork and thumbnails.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
from sqlalchemy.orm import selectinload
from app.database import SessionLocal
from app.models import Stream, StreamMetadata
from .image_download_service import ImageDownloadService

logger = logging.getLogger("streamvault")


class StreamArtworkService:
    """Handles stream artwork and thumbnail management"""

    def __init__(self, download_service: Optional[ImageDownloadService] = None):
        self.download_service = download_service or ImageDownloadService()
        self.artwork_dir = None
        self._ensure_artwork_dir()

    def _ensure_artwork_dir(self):
        """Ensure artwork directory exists"""
        if self.artwork_dir is None:
            images_base_dir = self.download_service.get_images_base_dir()
            self.artwork_dir = images_base_dir / "artwork"
            self.artwork_dir.mkdir(parents=True, exist_ok=True)

    def _get_streamer_artwork_dir(self, streamer_id: int) -> Path:
        """Get artwork directory for a specific streamer"""
        self._ensure_artwork_dir()
        streamer_dir = self.artwork_dir / f"streamer_{streamer_id}"
        streamer_dir.mkdir(parents=True, exist_ok=True)
        return streamer_dir

    async def download_stream_artwork(self, stream_id: int, streamer_id: int, thumbnail_url: str) -> Optional[str]:
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
            streamer_dir = self._get_streamer_artwork_dir(streamer_id)
            filename = f"stream_{stream_id}.jpg"
            file_path = streamer_dir / filename

            # Check if already exists
            if file_path.exists():
                return f"/data/images/artwork/streamer_{streamer_id}/{filename}"

            success = await self.download_service.download_image(thumbnail_url, file_path)
            if success:
                relative_path = f"/data/images/artwork/streamer_{streamer_id}/{filename}"
                logger.info(f"Successfully cached stream artwork for stream {stream_id}")
                return relative_path
            else:
                logger.warning(f"Failed to download stream artwork for stream {stream_id}")
                self.download_service.mark_download_failed(thumbnail_url)
                return None

        except Exception as e:
            logger.error(f"Error downloading stream artwork for stream {stream_id}: {e}")
            self.download_service.mark_download_failed(thumbnail_url)
            return None

    def get_cached_stream_artwork(self, stream_id: int, streamer_id: int) -> Optional[str]:
        """Get cached stream artwork path"""
        streamer_dir = self._get_streamer_artwork_dir(streamer_id)
        filename = f"stream_{stream_id}.jpg"
        file_path = streamer_dir / filename

        if file_path.exists():
            return f"/data/images/artwork/streamer_{streamer_id}/{filename}"
        return None

    async def update_stream_artwork(self, stream_id: int, thumbnail_url: str) -> bool:
        """Update a stream's artwork in database and cache"""
        try:
            # Get stream info
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    return False

                # Download the image
                cached_path = await self.download_stream_artwork(stream_id, stream.streamer_id, thumbnail_url)

                if cached_path:
                    # Ensure stream has metadata
                    if not stream.stream_metadata:
                        metadata = StreamMetadata(stream_id=stream_id)
                        db.add(metadata)
                        stream.stream_metadata = metadata

                    # Update metadata with cached path
                    stream.stream_metadata.thumbnail_url = cached_path
                    db.commit()
                    logger.info(f"Updated stream artwork for stream {stream_id}")
                    return True

            return False
        except Exception as e:
            logger.error(f"Error updating stream artwork for stream {stream_id}: {e}")
            return False

    async def sync_stream_artwork(self, stream_ids: List[int] = None) -> Dict[str, int]:
        """Sync stream artwork for specified streams or all streams"""
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}

        try:
            with SessionLocal() as db:
                # Load streams with their metadata
                query = db.query(Stream).options(selectinload(Stream.stream_metadata))
                if stream_ids:
                    query = query.filter(Stream.id.in_(stream_ids))

                streams = query.all()

                for stream in streams:
                    # Check if stream has metadata with thumbnail_url
                    thumbnail_url = None
                    if stream.stream_metadata and stream.stream_metadata.thumbnail_url:
                        thumbnail_url = stream.stream_metadata.thumbnail_url

                    if thumbnail_url and thumbnail_url.startswith("http"):
                        # This is a Twitch URL, download and cache it
                        cached_path = await self.download_stream_artwork(stream.id, stream.streamer_id, thumbnail_url)
                        if cached_path:
                            # Update to use cached path
                            stream.stream_metadata.thumbnail_url = cached_path
                            stats["downloaded"] += 1
                        else:
                            stats["failed"] += 1
                    else:
                        stats["skipped"] += 1

                db.commit()

        except Exception as e:
            logger.error(f"Error syncing stream artwork: {e}")

        logger.info(f"Stream artwork sync completed: {stats}")
        return stats

    async def bulk_download_artwork(self, artwork_data: List[Dict]) -> Dict[str, int]:
        """Bulk download stream artwork from provided data"""
        stats = {"downloaded": 0, "failed": 0}

        for artwork_info in artwork_data:
            stream_id = artwork_info.get("stream_id")
            streamer_id = artwork_info.get("streamer_id")
            thumbnail_url = artwork_info.get("thumbnail_url")

            if not all([stream_id, streamer_id, thumbnail_url]):
                continue

            cached_path = await self.download_stream_artwork(stream_id, streamer_id, thumbnail_url)
            if cached_path:
                stats["downloaded"] += 1
            else:
                stats["failed"] += 1

        logger.info(f"Bulk artwork download completed: {stats}")
        return stats

    def get_artwork_cache_stats(self) -> Dict[str, int]:
        """Get statistics about artwork cache"""
        try:
            self._ensure_artwork_dir()

            total_files = 0
            streamer_count = 0

            for streamer_dir in self.artwork_dir.glob("streamer_*"):
                if streamer_dir.is_dir():
                    streamer_count += 1
                    total_files += len(list(streamer_dir.glob("*.jpg")))

            return {
                "cached_artworks": total_files,
                "streamers_with_artwork": streamer_count,
                "failed_downloads": len(
                    [url for url in self.download_service._failed_downloads if "thumbnail" in url or "artwork" in url]
                ),
            }
        except Exception as e:
            logger.error(f"Error getting artwork cache stats: {e}")
            return {"cached_artworks": 0, "streamers_with_artwork": 0, "failed_downloads": 0}

    async def cleanup_old_artwork(self, days_old: int = 30) -> int:
        """Remove artwork files older than specified days"""
        from datetime import datetime, timedelta

        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)

        try:
            self._ensure_artwork_dir()

            for streamer_dir in self.artwork_dir.glob("streamer_*"):
                if streamer_dir.is_dir():
                    for artwork_file in streamer_dir.glob("*.jpg"):
                        try:
                            # Check file modification time
                            file_time = datetime.fromtimestamp(artwork_file.stat().st_mtime)
                            if file_time < cutoff_date:
                                artwork_file.unlink()
                                cleaned_count += 1
                                logger.debug(f"Removed old artwork: {artwork_file}")
                        except Exception as e:
                            logger.error(f"Error checking/removing artwork file {artwork_file}: {e}")

                    # Remove empty directories
                    try:
                        if not any(streamer_dir.iterdir()):
                            streamer_dir.rmdir()
                            logger.debug(f"Removed empty artwork directory: {streamer_dir}")
                    except Exception as e:
                        logger.error(f"Error removing empty directory {streamer_dir}: {e}")

        except Exception as e:
            logger.error(f"Error during artwork cleanup: {e}")

        logger.info(f"Cleaned up {cleaned_count} old artwork files")
        return cleaned_count

    async def cleanup_unused_artwork(self) -> int:
        """Remove artwork that is no longer associated with any stream"""
        cleaned_count = 0

        try:
            self._ensure_artwork_dir()

            # Get all stream IDs from database
            with SessionLocal() as db:
                active_stream_ids = set(str(s.id) for s in db.query(Stream.id).all())

            for streamer_dir in self.artwork_dir.glob("streamer_*"):
                if streamer_dir.is_dir():
                    for artwork_file in streamer_dir.glob("stream_*.jpg"):
                        try:
                            stream_id = artwork_file.stem.replace("stream_", "")

                            if stream_id not in active_stream_ids:
                                artwork_file.unlink()
                                cleaned_count += 1
                                logger.debug(f"Removed unused artwork: {artwork_file.name}")
                        except Exception as e:
                            logger.error(f"Error removing artwork file {artwork_file}: {e}")

        except Exception as e:
            logger.error(f"Error during artwork cleanup: {e}")

        logger.info(f"Cleaned up {cleaned_count} unused artwork files")
        return cleaned_count

    async def close(self):
        """Close the download service"""
        await self.download_service.close()
