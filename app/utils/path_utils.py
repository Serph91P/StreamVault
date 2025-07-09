"""Path utility functions for StreamVault."""
import os
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import extract
from app.database import SessionLocal

logger = logging.getLogger("streamvault")

# Filename presets for different media server structures
FILENAME_PRESETS = {
    "default": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "emby": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "jellyfin": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "kodi": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - E{episode:02d} - {title} - {hour}-{minute}"
}

def get_episode_number(streamer_id: int, now: datetime) -> str:
    """
    Get episode number (count of streams in current month).
    
    This method finds the highest existing episode number for the current month
    and adds 1, rather than just counting all streams. This prevents issues
    when streams are deleted from the filesystem but remain in the database.
    
    Args:
        streamer_id: ID of the streamer
        now: Current datetime
        
    Returns:
        Episode number as a two-digit string
    """
    try:
        from app.models import Stream
        
        with SessionLocal() as db:
            # Find the highest episode number for the current month
            streams = (
                db.query(Stream)
                .filter(
                    Stream.streamer_id == streamer_id,
                    extract("year", Stream.started_at) == now.year,
                    extract("month", Stream.started_at) == now.month,
                )
                .order_by(Stream.started_at.desc())
                .all()
            )
            
            # Find highest episode number from existing recording paths
            max_episode = 0
            current_month_year = f"{now.year}{now.month:02d}"
            
            for stream in streams:
                if stream.recording_path and "S" in stream.recording_path and "E" in stream.recording_path:
                    try:
                        # Extract episode number from path like "S202507E02"
                        import re
                        match = re.search(rf'S{current_month_year}E(\d+)', stream.recording_path)
                        if match:
                            episode_num = int(match.group(1))
                            max_episode = max(max_episode, episode_num)
                    except (ValueError, AttributeError):
                        continue
            
            # If no existing episodes found, also check filesystem for safety
            if max_episode == 0:
                try:
                    from app.config.settings import get_settings
                    settings = get_settings()
                    output_directory = getattr(settings, 'output_directory', '/recordings')
                    
                    # Get streamer name
                    from app.models import Streamer
                    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                    if streamer:
                        streamer_dir = os.path.join(output_directory, streamer.username)
                        season_dir = os.path.join(streamer_dir, f"Season {now.year}-{now.month:02d}")
                        
                        if os.path.exists(season_dir):
                            import re
                            for filename in os.listdir(season_dir):
                                match = re.search(rf'S{current_month_year}E(\d+)', filename)
                                if match:
                                    episode_num = int(match.group(1))
                                    max_episode = max(max_episode, episode_num)
                except Exception as fs_error:
                    logger.debug(f"Could not check filesystem for episodes: {fs_error}")
            
            # Next episode number
            episode_number = max_episode + 1
            
            logger.debug(
                f"Episode number for streamer {streamer_id} in {now.year}-{now.month:02d}: {episode_number} (max existing: {max_episode})"
            )
            return f"{episode_number:02d}"  # Format with leading zero

    except Exception as e:
        logger.error(f"Error getting episode number: {e}", exc_info=True)
        return "01"  # Default value

def generate_filename(
    streamer: Any, stream_data: Dict[str, Any], template: str, sanitize_func=None
) -> str:
    """
    Generate a filename from template with variables.
    
    Args:
        streamer: Streamer object
        stream_data: Stream data dictionary
        template: Filename template
        sanitize_func: Optional function to sanitize filenames
        
    Returns:
        Generated filename
    """
    from app.utils.file_utils import sanitize_filename as default_sanitize
    
    sanitize = sanitize_func or default_sanitize
    now = datetime.now()

    # Sanitize values for filesystem safety
    title = sanitize(stream_data.get("title", "untitled"))
    game = sanitize(stream_data.get("category_name", "unknown"))
    streamer_name = sanitize(streamer.username)

    # Get episode number (count of streams in current month)
    episode = get_episode_number(streamer.id, now)

    # Create a dictionary of replaceable values
    values = {
        "streamer": streamer_name,
        "title": title,
        "game": game,
        "twitch_id": streamer.twitch_id,
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "hour": now.strftime("%H"),
        "minute": now.strftime("%M"),
        "second": now.strftime("%S"),
        "timestamp": now.strftime("%Y%m%d_%H%M%S"),
        "datetime": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "id": stream_data.get("id", ""),
        "season": f"S{now.year}{now.month:02d}",  # Season without hyphen
        "episode": episode,  # Episode number without prefix, templates already include E
    }

    # Check if template is a preset name
    if template in FILENAME_PRESETS:
        template = FILENAME_PRESETS[template]
        
    # Use Python's format string system for replacements
    # This allows for complex formatting like {episode:02d}
    filename = template  # Initialize filename variable
    try:
        # First try Python's format method for complex placeholders
        filename = template.format(**values)
    except Exception as e:
        logger.warning(f"Error in format creation, trying fallback method: {e}")
        # Fallback in case complex formatting fails
        filename = template
        for key, value in values.items():
            # Try different possible format strings
            formats_to_try = [
                f"{{{key}}}",                # {episode}
                f"{{{key}:02d}}",            # {episode:02d}
                f"{{{key}:2d}}",             # {episode:2d}
                f"{{{key}:d}}",              # {episode:d}
            ]
            for fmt in formats_to_try:
                if fmt in filename:
                    if fmt.endswith(':02d}') and isinstance(value, str) and value.isdigit():
                        # For numbers as strings with 02d format
                        filename = filename.replace(fmt, f"{int(value):02d}")
                    else:
                        filename = filename.replace(fmt, str(value))

    # Ensure the filename ends with .mp4
    if not filename.lower().endswith(".mp4"):
        filename += ".mp4"
    return filename

async def update_recording_path(stream_id: int, new_path: str):
    """
    Update the recording path for a stream after media server structure creation.
    
    Args:
        stream_id: ID of the stream
        new_path: New path for the recording
    """
    try:
        from app.models import Stream
        
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if stream:
                old_path = stream.recording_path
                stream.recording_path = new_path
                db.commit()
                logger.info(f"Updated recording_path for stream {stream_id}: {old_path} -> {new_path}")
            else:
                logger.warning(f"Stream {stream_id} not found for recording_path update")
    except Exception as e:
        logger.error(f"Error updating recording_path for stream {stream_id}: {e}", exc_info=True)
