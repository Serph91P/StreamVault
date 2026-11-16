import logging
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Stream, Streamer
from app.services.http_client import HTTPPolicy, ManagedHTTPClient
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


class ArtworkService:
    """Service for managing artwork and metadata files separately from recordings"""

    def __init__(
        self,
        *,
        recordings_dir: Path = Path("/recordings"),
        download_image: Callable[[str, Path], Awaitable[bool]] | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.recordings_dir = recordings_dir
        self._image_downloader = download_image
        self._session_factory = session_factory
        self._http: ManagedHTTPClient | None = None
        self.media_base_path = self.recordings_dir / ".media"
        self.artwork_base_path = self.media_base_path / "artwork"
        self._initialized = False

    def _ensure_dirs(self) -> None:
        """Lazily create directories only when needed"""
        if self._initialized:
            return
        try:
            self.media_base_path.mkdir(parents=True, exist_ok=True)
            self.artwork_base_path.mkdir(parents=True, exist_ok=True)
            self._initialized = True
        except PermissionError:
            # Running in test environment without /recordings
            pass

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()
            self._http = None

    def get_streamer_artwork_dir(self, streamer_username: str) -> Path:
        """Get the artwork directory for a specific streamer"""
        self._ensure_dirs()
        safe_username = self._sanitize_filename(streamer_username)
        artwork_dir = self.artwork_base_path / safe_username
        artwork_dir.mkdir(parents=True, exist_ok=True)
        return artwork_dir

    def get_streamer_metadata_dir(self, streamer_username: str) -> Path:
        """Get the metadata directory for a specific streamer"""
        self._ensure_dirs()
        safe_username = self._sanitize_filename(streamer_username)
        metadata_dir = self.media_base_path / "metadata" / safe_username
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return metadata_dir

    def get_relative_artwork_path(self, streamer_username: str, filename: str) -> str:
        """Get relative path for artwork files (for NFO files)"""
        safe_username = self._sanitize_filename(streamer_username)
        return f".media/artwork/{safe_username}/{filename}"

    def _sessions(self) -> Session:
        return (self._session_factory or SessionLocal)()

    @staticmethod
    def _streamer_identity(streamer: Streamer) -> int | None:
        """Read cached identity without lazy I/O before constructing a coroutine."""
        try:
            identity = inspect(streamer).identity
        except NoInspectionAvailable:
            return None
        if identity is None or len(identity) != 1:
            return None
        return identity[0] if isinstance(identity[0], int) else None

    def save_streamer_artwork(self, streamer: Streamer) -> Awaitable[bool]:
        return self._save_artwork_by_id(self._streamer_identity(streamer))

    def _read_artwork(
        self, streamer_id: int
    ) -> tuple[str, str | None, str | None] | None:
        with self._sessions() as db:
            streamer = db.get(Streamer, streamer_id)
            if streamer is None:
                return None
            return (
                streamer.username,
                streamer.original_profile_image_url or streamer.profile_image_url,
                streamer.original_offline_image_url or streamer.offline_image_url,
            )

    async def _save_artwork_by_id(self, streamer_id: int | None) -> bool:
        if streamer_id is None:
            return False
        values = await run_in_thread_pool(self._read_artwork, streamer_id)
        return await self.save_artwork(*values) if values is not None else False

    async def save_artwork(
        self, username: str, profile_url: str | None, banner_url: str | None
    ) -> bool:
        """Save all artwork files for a streamer in the artwork directory

        Uses profile image for portrait artwork (poster, logo) and
        banner/offline image for landscape artwork (fanart, banner).

        Args:
            streamer: Streamer object

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not profile_url:
                logger.warning(f"No profile image URL for streamer {username}")
                return False

            artwork_dir = await run_in_thread_pool(
                self.get_streamer_artwork_dir, username
            )

            # Portrait artwork (square profile image works well)
            portrait_files = {
                "poster.jpg": "Main poster for the show",
                "logo.jpg": "Logo image",
                "clearlogo.jpg": "Clear logo image",
                "season.jpg": "Season poster",
                "season-poster.jpg": "Season poster alternative name",
                "folder.jpg": "Folder image for Windows",
                "show.jpg": "Show image",
            }

            # Landscape artwork (banner/fanart - use offline_image if available)
            landscape_files = {
                "banner.jpg": "Banner image",
                "fanart.jpg": "Background image",
            }

            success_count = 0

            # Download portrait artwork from profile image
            for filename, description in portrait_files.items():
                target_path = artwork_dir / filename
                if await self._download_image(profile_url, target_path):
                    success_count += 1
                    logger.debug(f"Saved {description} for {username} at {target_path}")

            # Download landscape artwork from banner (or fallback to profile)
            landscape_url = banner_url if banner_url else profile_url
            for filename, description in landscape_files.items():
                target_path = artwork_dir / filename
                if await self._download_image(landscape_url, target_path):
                    success_count += 1
                    logger.debug(f"Saved {description} for {username} at {target_path}")

            return success_count > 0

        except Exception as e:
            logger.error(f"Error saving streamer artwork: {e}", exc_info=True)
            return False

    def save_streamer_metadata(self, streamer: Streamer) -> Awaitable[bool]:
        return run_in_thread_pool(
            self._save_metadata_by_id, self._streamer_identity(streamer)
        )

    def _save_metadata_by_id(self, streamer_id: int | None) -> bool:
        if streamer_id is None:
            return False
        try:
            with self._sessions() as db:
                streamer = db.get(Streamer, streamer_id)
                if streamer is None:
                    return False
                metadata_dir = self.get_streamer_metadata_dir(streamer.username)
                if not self._create_tvshow_nfo(streamer, metadata_dir / "tvshow.nfo"):
                    return False
                return self._create_season_metadata_files(db, streamer, metadata_dir)
        except Exception as error:
            logger.error("Streamer metadata failed (%s)", type(error).__name__)
            return False

    def _create_tvshow_nfo(self, streamer: Streamer, nfo_path: Path) -> bool:
        """Create tvshow.nfo file for the streamer"""
        try:
            # Use relative paths for artwork - media servers expect paths relative to the NFO
            # Artwork is stored in .media/artwork/{username}/ at the recordings root
            safe_username = self._sanitize_filename(streamer.username)
            artwork_rel_path = f".media/artwork/{safe_username}"

            # Create XML content with relative paths
            tvshow_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>{streamer.username}</title>
    <originaltitle>{streamer.username}</originaltitle>
    <plot>Live streams and recordings from Twitch streamer {streamer.username}</plot>
    <mpaa>Not Rated</mpaa>
    <premiered>{streamer.created_at.strftime("%Y-%m-%d") if streamer.created_at else "Unknown"}</premiered>
    <studio>Twitch</studio>
    <genre>Gaming</genre>
    <genre>Entertainment</genre>
    <status>Continuing</status>
    <thumb aspect="poster">{artwork_rel_path}/poster.jpg</thumb>
    <thumb aspect="banner">{artwork_rel_path}/banner.jpg</thumb>
    <fanart>
        <thumb>{artwork_rel_path}/fanart.jpg</thumb>
    </fanart>
    <uniqueid type="twitch">{streamer.id}</uniqueid>
</tvshow>"""

            with open(nfo_path, "w", encoding="utf-8") as f:
                f.write(tvshow_content)

            logger.debug(f"Created tvshow.nfo: {nfo_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating tvshow.nfo: {e}")
            return False

    def _create_season_metadata_files(
        self, db: Session, streamer: Streamer, metadata_dir: Path
    ) -> bool:
        """Create season metadata files for all seasons (year-month combinations)"""
        try:
            streams = (
                db.query(Stream.started_at)
                .filter(
                    Stream.streamer_id == streamer.id, Stream.started_at.isnot(None)
                )
                .yield_per(1000)
            )
            season_combinations = {
                (started_at.year, started_at.month)
                for (started_at,) in streams
                if started_at is not None
            }
            success = True
            for year, month in sorted(season_combinations):
                season_dir = metadata_dir / f"Season_{year}-{month:02d}"
                season_dir.mkdir(parents=True, exist_ok=True)
                if not self._create_season_nfo(
                    streamer, year, month, season_dir / "season.nfo"
                ):
                    success = False
            return success

        except Exception as e:
            logger.error(f"Error creating season metadata files: {e}", exc_info=True)
            return False

    def _create_season_nfo(
        self, streamer: Streamer, year: int, month: int, nfo_path: Path
    ) -> bool:
        """Create season.nfo file for a specific year-month combination"""
        try:
            # Use relative paths for artwork
            safe_username = self._sanitize_filename(streamer.username)
            artwork_rel_path = f".media/artwork/{safe_username}"

            season_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<season>
    <title>{streamer.username} - {year}-{month:02d}</title>
    <plot>Streams from {streamer.username} in {year}-{month:02d}</plot>
    <seasonnumber>{year}{month:02d}</seasonnumber>
    <premiered>{year}-{month:02d}-01</premiered>
    <thumb aspect="poster">{artwork_rel_path}/season.jpg</thumb>
    <fanart>
        <thumb>{artwork_rel_path}/fanart.jpg</thumb>
    </fanart>
</season>"""

            with open(nfo_path, "w", encoding="utf-8") as f:
                f.write(season_content)

            logger.debug(f"Created season.nfo: {nfo_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating season.nfo: {e}")
            return False

    def _prepare_image(self, url: str, target_path: Path) -> bool | None:
        if target_path.exists():
            return True
        is_local = (
            url.startswith("/")
            or (len(url) >= 3 and url[1] == ":" and url[2] == "\\")
            or url.startswith("\\\\")
            or Path(url).is_absolute()
        )
        if not is_local:
            return None
        source = Path(url)
        if url.startswith("/data/images/profiles/"):
            source = self.recordings_dir / ".media" / "profiles" / url.split("/")[-1]
        if not source.exists():
            return False
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target_path)
        return True

    @staticmethod
    def _write_image(target_path: Path, content: bytes) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as destination:
            destination.write(content)

    async def _download_image(self, url: str, target_path: Path) -> bool:
        """Download an image from a URL or copy from local path to a target path

        Returns:
            bool: True on success, False on error
        """
        if self._image_downloader is not None:
            if await run_in_thread_pool(target_path.exists):
                return True
            if url.startswith("/data/images/profiles/"):
                url = str(
                    self.recordings_dir / ".media" / "profiles" / url.split("/")[-1]
                )
            return await self._image_downloader(url, target_path)
        try:
            prepared = await run_in_thread_pool(self._prepare_image, url, target_path)
            if prepared is not None:
                return prepared
            if self._http is None:
                self._http = ManagedHTTPClient(HTTPPolicy())
            async with self._http.stream("GET", url, follow_redirects=True) as response:
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "image" in content_type:
                        content = b"".join([chunk async for chunk in response.chunks])

                        await run_in_thread_pool(
                            self._write_image, target_path, content
                        )

                        logger.debug(f"Downloaded image: {target_path}")
                        return True
                    else:
                        logger.warning(
                            f"Invalid content type for image: {content_type}"
                        )
                        return False
                else:
                    logger.warning("Image HTTP failed: status=%s", response.status_code)
                    return False

        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return False

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem use"""
        import re

        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(". ")
        return sanitized or "unknown"


# Global instance
artwork_service = ArtworkService()
