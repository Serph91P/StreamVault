import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Stream, Streamer
from app.config.settings import settings
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")

class ArtworkService:
    """Service for managing artwork and metadata files separately from recordings"""
    
    def __init__(self):
        self.artwork_base_path = Path(settings.ARTWORK_BASE_PATH)
        # Ensure the artwork directory exists
        self.artwork_base_path.mkdir(parents=True, exist_ok=True)
    
    async def close(self):
        """Close resources (now handled by unified_image_service)"""
        pass
    
    def get_streamer_artwork_dir(self, streamer_username: str) -> Path:
        """Get the artwork directory for a specific streamer"""
        safe_username = self._sanitize_filename(streamer_username)
        artwork_dir = self.artwork_base_path / safe_username
        artwork_dir.mkdir(parents=True, exist_ok=True)
        return artwork_dir
    
    def get_streamer_metadata_dir(self, streamer_username: str) -> Path:
        """Get the metadata directory for a specific streamer"""
        safe_username = self._sanitize_filename(streamer_username)
        metadata_dir = self.artwork_base_path / safe_username / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return metadata_dir
    
    async def save_streamer_artwork(self, streamer: Streamer) -> bool:
        """Save all artwork files for a streamer in the artwork directory
        
        Args:
            streamer: Streamer object
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not streamer.profile_image_url:
                logger.warning(f"No profile image URL for streamer {streamer.username}")
                return False
            
            artwork_dir = self.get_streamer_artwork_dir(streamer.username)
            
            # Standard media server image names
            image_files = {
                "poster.jpg": "Main poster for the show",
                "banner.jpg": "Banner image", 
                "fanart.jpg": "Background image",
                "logo.jpg": "Logo image",
                "clearlogo.jpg": "Clear logo image",
                "season.jpg": "Season poster",
                "season-poster.jpg": "Season poster alternative name",
                "folder.jpg": "Folder image for Windows",
                "show.jpg": "Show image"
            }
            
            # Download and save each image format
            success_count = 0
            for filename, description in image_files.items():
                target_path = artwork_dir / filename
                if await self._download_image(streamer.profile_image_url, target_path):
                    success_count += 1
                    logger.debug(f"Saved {description} for {streamer.username} at {target_path}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error saving streamer artwork: {e}", exc_info=True)
            return False
    
    async def save_streamer_metadata(self, streamer: Streamer) -> bool:
        """Save metadata files for a streamer in the metadata directory
        
        Args:
            streamer: Streamer object
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            metadata_dir = self.get_streamer_metadata_dir(streamer.username)
            
            # Create tvshow.nfo
            tvshow_nfo_path = metadata_dir / "tvshow.nfo"
            await self._create_tvshow_nfo(streamer, tvshow_nfo_path)
            
            # Create season.nfo for each year/month combination
            await self._create_season_metadata_files(streamer, metadata_dir)
            
            logger.info(f"Successfully saved metadata for {streamer.username} in {metadata_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving streamer metadata: {e}", exc_info=True)
            return False
    
    async def _create_tvshow_nfo(self, streamer: Streamer, nfo_path: Path):
        """Create tvshow.nfo file for the streamer"""
        try:
            artwork_dir = self.get_streamer_artwork_dir(streamer.username)
            
            # Create XML content
            tvshow_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>{streamer.username}</title>
    <originaltitle>{streamer.username}</originaltitle>
    <plot>Live streams and recordings from Twitch streamer {streamer.username}</plot>
    <mpaa>Not Rated</mpaa>
    <premiered>{streamer.created_at.strftime('%Y-%m-%d') if streamer.created_at else 'Unknown'}</premiered>
    <studio>Twitch</studio>
    <genre>Gaming</genre>
    <genre>Entertainment</genre>
    <status>Continuing</status>
    <thumb aspect="poster">{artwork_dir / 'poster.jpg'}</thumb>
    <thumb aspect="banner">{artwork_dir / 'banner.jpg'}</thumb>
    <fanart>
        <thumb>{artwork_dir / 'fanart.jpg'}</thumb>
    </fanart>
    <uniqueid type="twitch">{streamer.id}</uniqueid>
</tvshow>"""
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(tvshow_content)
            
            logger.debug(f"Created tvshow.nfo: {nfo_path}")
            
        except Exception as e:
            logger.error(f"Error creating tvshow.nfo: {e}", exc_info=True)
    
    async def _create_season_metadata_files(self, streamer: Streamer, metadata_dir: Path):
        """Create season metadata files for all seasons (year-month combinations)"""
        try:
            with SessionLocal() as db:
                # Get all unique year-month combinations for this streamer
                streams = db.query(Stream).filter(
                    Stream.streamer_id == streamer.id,
                    Stream.started_at.isnot(None)
                ).all()
                
                season_combinations = set()
                for stream in streams:
                    if stream.started_at:
                        year_month = (stream.started_at.year, stream.started_at.month)
                        season_combinations.add(year_month)
                
                # Create season.nfo for each combination
                for year, month in season_combinations:
                    season_dir = metadata_dir / f"Season_{year}-{month:02d}"
                    season_dir.mkdir(parents=True, exist_ok=True)
                    
                    season_nfo_path = season_dir / "season.nfo"
                    await self._create_season_nfo(streamer, year, month, season_nfo_path)
                    
        except Exception as e:
            logger.error(f"Error creating season metadata files: {e}", exc_info=True)
    
    async def _create_season_nfo(self, streamer: Streamer, year: int, month: int, nfo_path: Path):
        """Create season.nfo file for a specific year-month combination"""
        try:
            artwork_dir = self.get_streamer_artwork_dir(streamer.username)
            
            season_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<season>
    <title>{streamer.username} - {year}-{month:02d}</title>
    <plot>Streams from {streamer.username} in {year}-{month:02d}</plot>
    <seasonnumber>{year}{month:02d}</seasonnumber>
    <premiered>{year}-{month:02d}-01</premiered>
    <thumb aspect="poster">{artwork_dir / 'season.jpg'}</thumb>
    <fanart>
        <thumb>{artwork_dir / 'fanart.jpg'}</thumb>
    </fanart>
</season>"""
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(season_content)
            
            logger.debug(f"Created season.nfo: {nfo_path}")
            
        except Exception as e:
            logger.error(f"Error creating season.nfo: {e}", exc_info=True)
    
    async def _download_image(self, url: str, target_path: Path) -> bool:
        """Download an image from a URL to a target path
        
        Returns:
            bool: True on success, False on error
        """
        try:
            if target_path.exists():
                logger.debug(f"Image already exists: {target_path}")
                return True
            
            # Use unified_image_service for download
            session = await unified_image_service._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type:
                        content = await response.read()
                        
                        # Create parent directory if it doesn't exist
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(target_path, 'wb') as f:
                            f.write(content)
                        
                        logger.debug(f"Downloaded image: {target_path}")
                        return True
                    else:
                        logger.warning(f"Invalid content type for image: {content_type}")
                        return False
                else:
                    logger.warning(f"Failed to download image: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem use"""
        import re
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip('. ')
        return sanitized or "unknown"

# Global instance
artwork_service = ArtworkService()
