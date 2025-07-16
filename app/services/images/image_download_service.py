"""
ImageDownloadService - HTTP download operations and session management

Extracted from unified_image_service.py God Class
Handles HTTP sessions, downloads, and common image operations.
"""

import aiohttp
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, Set
from app.services.recording.config_manager import ConfigManager

try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

logger = logging.getLogger("streamvault")


class ImageDownloadService:
    """Handles HTTP downloads and common image operations"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.config_manager = ConfigManager()
        self._failed_downloads: Set[str] = set()
        
        # Initialize directories
        self._initialized = False
        self.recordings_dir = None
        self.images_base_dir = None
        
    def _ensure_initialized(self):
        """Ensure the service is initialized (lazy initialization)"""
        if not self._initialized:
            try:
                # Get recordings directory from config
                self.recordings_dir = Path(self.config_manager.get_recordings_directory())
                
                # Create hidden .images directory in recordings
                self.images_base_dir = self.recordings_dir / ".images"
                self.images_base_dir.mkdir(parents=True, exist_ok=True)
                
                self._initialized = True
                logger.info(f"Image download service initialized, storage: {self.images_base_dir}")
            except Exception as e:
                logger.error(f"Failed to initialize image download service: {e}")
                # Fallback to a default directory if config fails
                self.recordings_dir = Path("/recordings")
                self.images_base_dir = self.recordings_dir / ".images"
                self.images_base_dir.mkdir(parents=True, exist_ok=True)
                self._initialized = True
                logger.warning(f"Image download service initialized with fallback directory: {self.images_base_dir}")

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename for filesystem"""
        # Replace special characters with underscores
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Replace spaces with underscores
        safe_name = safe_name.replace(' ', '_')
        # Remove multiple underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        return safe_name.strip('_').lower()
    
    def create_filename_hash(self, url: str) -> str:
        """Create a hash-based filename for an image URL"""
        return hashlib.md5(url.encode()).hexdigest()

    async def download_image(self, url: str, file_path: Path, expected_content_types: list = None) -> bool:
        """
        Download an image from URL to file path
        
        Args:
            url: Image URL to download
            file_path: Path where to save the image
            expected_content_types: List of expected content types (default: ['image'])
            
        Returns:
            True if download was successful, False otherwise
        """
        if not HAS_AIOFILES:
            logger.warning("aiofiles not available, cannot download image")
            return False
            
        if not url:
            return False
            
        # Skip if previously failed
        if url in self._failed_downloads:
            return False
            
        if expected_content_types is None:
            expected_content_types = ['image']
            
        try:
            session = await self.get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if any(ct in content_type for ct in expected_content_types):
                        # Ensure directory exists
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        logger.debug(f"Downloaded image: {url} -> {file_path}")
                        return True
                    else:
                        logger.warning(f"Invalid content type for {url}: {content_type}")
                else:
                    logger.warning(f"Failed to download image {url}: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            self._failed_downloads.add(url)
            
        return False

    def mark_download_failed(self, url: str):
        """Mark a URL as failed to avoid repeated attempts"""
        self._failed_downloads.add(url)

    def is_download_failed(self, url: str) -> bool:
        """Check if URL was previously marked as failed"""
        return url in self._failed_downloads

    def get_images_base_dir(self) -> Path:
        """Get the base images directory"""
        self._ensure_initialized()
        return self.images_base_dir
