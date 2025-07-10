import os
import shutil
import logging
import asyncio
import aiohttp
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Stream, StreamMetadata, Streamer, StreamEvent
from app.config.settings import settings
from app.services.artwork_service import artwork_service

logger = logging.getLogger("streamvault")

class MediaServerStructureService:
    """Service for creating optimized directory structures for media servers like Plex, Emby, Jellyfin"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Get recordings base path from database settings
        self.recordings_base = self._get_recordings_base_path()
    
    def _get_recordings_base_path(self) -> Path:
        """Get the recordings base path from database settings"""
        try:
            with SessionLocal() as db:
                from app.models import RecordingSettings
                settings_record = db.query(RecordingSettings).first()
                if settings_record and settings_record.output_directory:
                    return Path(settings_record.output_directory)
                return Path("/app/recordings")  # Default fallback
        except Exception as e:
            logger.warning(f"Failed to get recordings path from database: {e}")
            return Path("/app/recordings")  # Fallback
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def create_media_server_structure(
        self, 
        stream_id: int, 
        original_mp4_path: str
    ) -> Optional[str]:
        """
        Creates optimized media server structure and moves/copies files
        
        Args:
            stream_id: Stream ID
            original_mp4_path: Original path to MP4 file
            
        Returns:
            Optional[str]: New path to the MP4 file or None on error
        """
        try:
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.error(f"Stream {stream_id} not found")
                    return None
                
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer {stream.streamer_id} not found")
                    return None
                
                # Generate new filename and path structure
                new_structure = self._generate_media_server_paths(stream, streamer)
                if not new_structure:
                    logger.error("Failed to generate media server structure")
                    return None
                
                # Create directories
                await self._create_directory_structure(new_structure)
                
                # Move/copy the MP4 file
                new_mp4_path = await self._move_video_file(original_mp4_path, new_structure["episode_file"])
                if not new_mp4_path:
                    logger.error("Failed to move video file")
                    return None
                
                # Create all metadata files
                await self._create_all_metadata_files(stream, streamer, new_structure, db)
                
                # Save artwork and metadata to dedicated directories (not in recordings)
                await artwork_service.save_streamer_artwork(streamer)
                await artwork_service.save_streamer_metadata(streamer)
                
                # Download episode thumbnail (only for the recording)
                await self._create_episode_thumbnail(stream, streamer, new_structure["episode_thumb"])
                
                logger.info(f"Successfully created media server structure for {streamer.username}")
                return new_mp4_path
                
        except Exception as e:
            logger.error(f"Error creating media server structure: {e}", exc_info=True)
            return None
    
    def _generate_media_server_paths(self, stream: Stream, streamer: Streamer) -> Optional[Dict[str, str]]:
        """Generate all required paths for media server structure"""
        try:
            # Sanitize streamer name
            safe_streamer_name = self._sanitize_filename(streamer.username)
            
            # Generate season and episode info
            if stream.started_at:
                year = stream.started_at.year
                month = stream.started_at.month
                episode_num = self._get_episode_number(stream.streamer_id, stream.started_at)
            else:
                now = datetime.now(timezone.utc)
                year = now.year
                month = now.month
                episode_num = 1
            
            season_name = f"Season {year}-{month:02d}"
            episode_id = f"S{year}{month:02d}E{episode_num:02d}"
            
            # Clean title
            safe_title = self._sanitize_filename(stream.title or "Stream")
            
            # Generate filename (detect extension from actual file)
            original_ext = os.path.splitext(original_mp4_path)[1].lower()
            if original_ext not in ['.mp4', '.mkv']:
                # Default to mp4 if extension is unexpected
                original_ext = '.mp4'
            
            episode_filename = f"{safe_streamer_name} - {episode_id} - {safe_title}"
            
            # Build paths with correct extension
            streamer_dir = self.recordings_base / safe_streamer_name
            season_dir = streamer_dir / season_name
            
            return {
                "streamer_dir": str(streamer_dir),
                "season_dir": str(season_dir),
                "episode_file": str(season_dir / f"{episode_filename}{original_ext}"),
                "episode_nfo": str(season_dir / f"{episode_filename}.nfo"),
                "episode_thumb": str(season_dir / f"{episode_filename}-thumb.jpg"),
                "episode_chapters_vtt": str(season_dir / f"{episode_filename}.chapters.vtt"),
                "episode_chapters_xml": str(season_dir / f"{episode_filename}.chapters.xml"),
                "tvshow_nfo": str(streamer_dir / "tvshow.nfo"),
                "season_nfo": str(season_dir / "season.nfo"),
                "episode_info": {
                    "filename": episode_filename,
                    "episode_id": episode_id,
                    "season_name": season_name,
                    "episode_num": episode_num,
                    "year": year,
                    "month": month,
                    "format": original_ext[1:]  # Remove the dot
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating media server paths: {e}", exc_info=True)
            return None
    
    async def _create_directory_structure(self, structure: Dict[str, Any]):
        """Create all required directories"""
        try:
            os.makedirs(structure["streamer_dir"], exist_ok=True)
            os.makedirs(structure["season_dir"], exist_ok=True)
            logger.debug(f"Created directories: {structure['streamer_dir']}, {structure['season_dir']}")
        except Exception as e:
            logger.error(f"Error creating directories: {e}", exc_info=True)
            raise
    
    async def _move_video_file(self, source_path: str, target_path: str) -> Optional[str]:
        """Move video file to new location"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file does not exist: {source_path}")
                return None
            
            # Create target directory if it doesn't exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Move the file
            shutil.move(source_path, target_path)
            logger.info(f"Moved video file from {source_path} to {target_path}")
            
            return target_path
            
        except Exception as e:
            logger.error(f"Error moving video file: {e}", exc_info=True)
            return None
    
    async def _create_all_metadata_files(
        self, 
        stream: Stream, 
        streamer: Streamer, 
        structure: Dict[str, Any],
        db: Session
    ):
        """Create all NFO and metadata files"""
        try:
            # Create tvshow.nfo (defensive check)
            if "tvshow_nfo" in structure:
                await self._create_tvshow_nfo(streamer, structure["tvshow_nfo"])
            else:
                logger.warning("tvshow_nfo path not found in structure")
            
            # Create season.nfo (defensive check)
            if "season_nfo" in structure and "episode_info" in structure:
                await self._create_season_nfo(
                    streamer, 
                    structure["episode_info"]["year"], 
                    structure["episode_info"]["month"],
                    structure["season_nfo"]
                )
            else:
                logger.warning("season_nfo or episode_info not found in structure")
            
            # Create episode.nfo
            await self._create_episode_nfo(stream, streamer, structure, db)
            
            # Create chapter files
            await self._create_chapter_files(stream, structure, db)
            
        except Exception as e:
            logger.error(f"Error creating metadata files: {e}", exc_info=True)
            raise
    
    async def _create_tvshow_nfo(self, streamer: Streamer, nfo_path: str):
        """Create tvshow.nfo file for the series"""
        try:
            # Only create if it doesn't exist
            if os.path.exists(nfo_path):
                logger.debug(f"tvshow.nfo already exists: {nfo_path}")
                return
            
            nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>{streamer.username}</title>
    <originaltitle>{streamer.username}</originaltitle>
    <plot>Twitch streams by {streamer.username}</plot>
    <genre>Gaming</genre>
    <genre>Live Stream</genre>
    <premiered>{datetime.now().year}</premiered>
    <studio>Twitch</studio>
    <thumb>poster.jpg</thumb>
    <fanart>poster.jpg</fanart>
    <uniqueid type="streamvault" default="true">streamer_{streamer.id}</uniqueid>
</tvshow>"""
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            logger.debug(f"Created tvshow.nfo: {nfo_path}")
            
        except Exception as e:
            logger.error(f"Error creating tvshow.nfo: {e}", exc_info=True)
            raise
    
    async def _create_season_nfo(self, streamer: Streamer, year: int, month: int, nfo_path: str):
        """Create season.nfo file"""
        try:
            # Only create if it doesn't exist
            if os.path.exists(nfo_path):
                logger.debug(f"season.nfo already exists: {nfo_path}")
                return
            
            season_num = f"{year}{month:02d}"
            
            nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<season>
    <seasonnumber>{season_num}</seasonnumber>
    <title>{streamer.username} - {year}-{month:02d}</title>
    <plot>Streams from {streamer.username} in {year}-{month:02d}</plot>
    <thumb>poster.jpg</thumb>
    <fanart>poster.jpg</fanart>
</season>"""
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            logger.debug(f"Created season.nfo: {nfo_path}")
            
        except Exception as e:
            logger.error(f"Error creating season.nfo: {e}", exc_info=True)
            raise
    
    async def _create_episode_nfo(
        self, 
        stream: Stream, 
        streamer: Streamer, 
        structure: Dict[str, Any],
        db: Session
    ):
        """Create episode.nfo file"""
        try:
            episode_info = structure["episode_info"]
            
            # Get runtime from stream duration if available
            runtime = ""
            if stream.started_at and stream.ended_at:
                duration_seconds = (stream.ended_at - stream.started_at).total_seconds()
                runtime_minutes = int(duration_seconds / 60)
                runtime = f"<runtime>{runtime_minutes}</runtime>"
            
            # Format air date
            aired = stream.started_at.strftime("%Y-%m-%d") if stream.started_at else datetime.now().strftime("%Y-%m-%d")
            
            # Create plot description
            plot_parts = [f"Twitch stream by {streamer.username}"]
            if stream.category_name:
                plot_parts.append(f"Category: {stream.category_name}")
            if stream.started_at and stream.ended_at:
                duration = stream.ended_at - stream.started_at
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                plot_parts.append(f"Duration: {hours}h {minutes}m")
            
            plot = " | ".join(plot_parts)
            
            nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{stream.title or 'Stream'}</title>
    <showtitle>{streamer.username}</showtitle>
    <season>{episode_info['year']}{episode_info['month']:02d}</season>
    <episode>{episode_info['episode_num']}</episode>
    <plot>{plot}</plot>
    <aired>{aired}</aired>
    {runtime}
    <studio>Twitch</studio>
    <genre>Gaming</genre>
    <genre>Live Stream</genre>
    <thumb>{os.path.basename(structure['episode_thumb'])}</thumb>
    <uniqueid type="streamvault" default="true">stream_{stream.id}</uniqueid>
</episodedetails>"""
            
            with open(structure["episode_nfo"], 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            logger.debug(f"Created episode.nfo: {structure['episode_nfo']}")
            
        except Exception as e:
            logger.error(f"Error creating episode.nfo: {e}", exc_info=True)
            raise
    
    async def _create_chapter_files(self, stream: Stream, structure: Dict[str, Any], db: Session):
        """Create chapter files in VTT and XML formats"""
        try:
            # Get stream events for chapters
            events = db.query(StreamEvent).filter(
                StreamEvent.stream_id == stream.id
            ).order_by(StreamEvent.timestamp).all()
            
            if events:
                # Create VTT chapters
                await self._create_vtt_chapters(stream, events, structure["episode_chapters_vtt"])
                
                # Create XML chapters
                await self._create_xml_chapters(stream, events, structure["episode_chapters_xml"])
            else:
                logger.debug(f"No events found for stream {stream.id}, skipping chapter creation")
                
        except Exception as e:
            logger.error(f"Error creating chapter files: {e}", exc_info=True)
    
    async def _create_vtt_chapters(self, stream: Stream, events: List[StreamEvent], vtt_path: str):
        """Create WebVTT chapter file"""
        try:
            with open(vtt_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                
                for i, event in enumerate(events):
                    # Calculate start time
                    if stream.started_at:
                        start_seconds = max(0, (event.timestamp - stream.started_at).total_seconds())
                    else:
                        start_seconds = 0
                    
                    # Calculate end time
                    if i < len(events) - 1:
                        end_seconds = (events[i + 1].timestamp - stream.started_at).total_seconds()
                    elif stream.ended_at:
                        end_seconds = (stream.ended_at - stream.started_at).total_seconds()
                    else:
                        end_seconds = start_seconds + 300  # 5 minutes default
                    
                    start_time = self._format_vtt_timestamp(start_seconds)
                    end_time = self._format_vtt_timestamp(end_seconds)
                    
                    title = event.title or "Stream"
                    if event.category_name:
                        title += f" - {event.category_name}"
                    
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{title}\n\n")
            
            logger.debug(f"Created VTT chapters: {vtt_path}")
            
        except Exception as e:
            logger.error(f"Error creating VTT chapters: {e}", exc_info=True)
    
    async def _create_xml_chapters(self, stream: Stream, events: List[StreamEvent], xml_path: str):
        """Create XML chapter file for Emby/Jellyfin"""
        try:
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<chapters>\n')
                
                for i, event in enumerate(events):
                    # Calculate start time in milliseconds
                    if stream.started_at:
                        start_ms = int(max(0, (event.timestamp - stream.started_at).total_seconds() * 1000))
                    else:
                        start_ms = 0
                    
                    title = event.title or "Stream"
                    if event.category_name:
                        title += f" - {event.category_name}"
                    
                    # Escape XML characters
                    title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    f.write(f'  <chapter start="{start_ms}" title="{title}" />\n')
                
                f.write('</chapters>\n')
            
            logger.debug(f"Created XML chapters: {xml_path}")
            
        except Exception as e:
            logger.error(f"Error creating XML chapters: {e}", exc_info=True)

    async def _create_episode_thumbnail(self, stream: Stream, streamer: Streamer, thumb_path: str):
        """Create episode thumbnail from Twitch or video extraction"""
        try:
            # Try to download from Twitch first
            thumbnail_url = f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{streamer.username}-1280x720.jpg"
            
            session = await self._get_session()
            async with session.get(thumbnail_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Check if it's a placeholder image
                    if len(content) > 5000:  # Reasonable size check
                        with open(thumb_path, 'wb') as f:
                            f.write(content)
                        logger.debug(f"Downloaded episode thumbnail from Twitch: {thumb_path}")
                        return
            
            # Fallback: Extract from video (this would need the video file path)
            logger.debug(f"Could not download Twitch thumbnail, would need video extraction")
            
        except Exception as e:
            logger.error(f"Error creating episode thumbnail: {e}", exc_info=True)
    
    def _get_episode_number(self, streamer_id: int, stream_date: datetime) -> int:
        """
        Get episode number for a stream within its month based on the actual stream.
        Uses the same logic as path_utils.get_episode_number to ensure consistency.
        """
        try:
            from app.utils.path_utils import get_episode_number
            episode_str = get_episode_number(streamer_id, stream_date)
            return int(episode_str)
                
        except Exception as e:
            logger.error(f"Error getting episode number: {e}", exc_info=True)
            return 1
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        if not filename:
            return "Unknown"
        
        # Replace problematic characters
        sanitized = filename
        for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            sanitized = sanitized.replace(char, '_')
        
        # Remove multiple spaces and trim
        sanitized = ' '.join(sanitized.split())
        
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip()
        
        return sanitized or "Unknown"
    
    def _format_vtt_timestamp(self, seconds: float) -> str:
        """Format timestamp for VTT format (HH:MM:SS.mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
