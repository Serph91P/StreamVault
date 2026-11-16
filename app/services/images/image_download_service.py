"""Owned image HTTP and worker-bound filesystem operations."""

import hashlib
from contextlib import ExitStack
import logging
import os
from pathlib import Path
import re
from typing import BinaryIO

from app.config.settings import Settings, get_settings
from app.services.http_client import HTTPClientError, HTTPPolicy, ManagedHTTPClient
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


class ImageDownloadService:
    """Image GETs have their own pool and explicitly opt into bounded redirects."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: ManagedHTTPClient | None = None,
    ) -> None:
        self.session = http_client
        self._owns_session = http_client is None
        self._closed = False
        self._failed_downloads: set[str] = set()
        self._initialized = False
        self.recordings_dir = Path((settings or get_settings()).RECORDING_DIRECTORY)
        self.images_base_dir = self.recordings_dir / ".media"

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.images_base_dir.mkdir(parents=True, exist_ok=True)
            for name in ("profiles", "categories", "artwork", "thumbnails"):
                (self.images_base_dir / name).mkdir(exist_ok=True)
            self._initialized = True

    async def get_session(self) -> ManagedHTTPClient:
        if self._closed:
            raise HTTPClientError("closed")
        if self.session is None:
            self.session = ManagedHTTPClient(HTTPPolicy())
        return self.session

    async def close(self) -> None:
        self._closed = True
        if self.session is not None and self._owns_session:
            await self.session.close()

    def sanitize_filename(self, name: str) -> str:
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
        safe_name = safe_name.replace(" ", "_")
        return re.sub(r"_+", "_", safe_name).strip("_").lower()

    def _resolve_destination_path(self, file_path: Path) -> Path:
        """Resolve a file below the media directory before any HTTP request."""
        self._ensure_initialized()
        media_dir = os.path.realpath(os.fspath(self.images_base_dir))
        destination = os.path.realpath(os.path.abspath(os.fspath(file_path)))
        try:
            is_contained = os.path.commonpath((media_dir, destination)) == media_dir
        except ValueError:
            is_contained = False
        if not is_contained or destination == media_dir:
            raise ValueError("Download destination is outside the media directory")
        return Path(destination)

    def create_filename_hash(self, url: str) -> str:
        return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()

    async def download_image(
        self,
        url: str,
        file_path: Path,
        expected_content_types: list[str] | None = None,
        *,
        retry_failed: bool = False,
    ) -> bool:
        if not url or self._closed:
            return False
        if not retry_failed and url in self._failed_downloads:
            return False
        if expected_content_types is None:
            expected_content_types = ["image"]
        try:

            def prepare_destination() -> Path:
                destination = self._resolve_destination_path(file_path)
                media_dir = os.path.realpath(os.fspath(self.images_base_dir))
                resolved = os.path.realpath(os.path.abspath(os.fspath(destination)))
                if not resolved.startswith(media_dir + os.sep):
                    raise ValueError(
                        "Download destination is outside the media directory"
                    )
                return Path(resolved)

            file_path = await run_in_thread_pool(prepare_destination)
            client = await self.get_session()
            async with client.stream("GET", url, follow_redirects=True) as response:
                if response.status_code != 200:
                    return False
                if not any(
                    value in response.headers.get("content-type", "")
                    for value in expected_content_types
                ):
                    logger.warning("Image response content type rejected")
                    return False
                destination = ExitStack()

                def open_destination() -> BinaryIO:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    writer = file_path.open("wb")
                    destination.callback(writer.close)
                    return writer

                try:
                    # Register cleanup inside the worker before cancellation can return.
                    writer = await run_in_thread_pool(open_destination)
                    async for chunk in response.chunks:
                        await run_in_thread_pool(writer.write, chunk)
                finally:
                    await run_in_thread_pool(destination.close)
            logger.debug("Image download completed")
            return True
        except HTTPClientError as error:
            # Legacy non-200 responses did not permanently blacklist a URL.
            if error.code != "status" and not retry_failed:
                self._failed_downloads.add(url)
            logger.warning(
                "Image HTTP failed: code=%s status=%s", error.code, error.status_code
            )
        except Exception as error:
            if not retry_failed:
                self._failed_downloads.add(url)
            logger.error("Image download failed: %s", type(error).__name__)
        return False

    def mark_download_failed(self, url: str) -> None:
        self._failed_downloads.add(url)

    def is_download_failed(self, url: str) -> bool:
        return url in self._failed_downloads

    def get_images_base_dir(self) -> Path:
        return self.images_base_dir
