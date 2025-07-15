"""Path utility functions for StreamVault."""
import os
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import extract
from app.database import SessionLocal
from app.utils import async_file

logger = logging.getLogger("streamvault")

# Filename presets for different media server structures
FILENAME_PRESETS = {
    "default": "{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "emby": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "jellyfin": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "kodi": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - E{episode:02d} - {title} - {hour}-{minute}"
}

async def get_episode_number(streamer_id: int, now: datetime) -> str:
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
            # Find the highest episode number for the current month using database storage
            max_episode_num = 0
            
            # Try to use episode_number column if it exists
            try:
                max_episode = (
                    db.query(Stream.episode_number)
                    .filter(
                        Stream.streamer_id == streamer_id,
                        extract("year", Stream.started_at) == now.year,
                        extract("month", Stream.started_at) == now.month,
                        Stream.episode_number.isnot(None)
                    )
                    .order_by(Stream.episode_number.desc())
                    .first()
                )
                
                max_episode_num = max_episode[0] if max_episode else 0
            except Exception as e:
                # If episode_number column doesn't exist, fall back to old method
                logger.debug(f"episode_number column not available, using fallback method: {e}")
                max_episode_num = 0
            
            # If no database episode numbers found, try to extract from existing recording paths as fallback
            if max_episode_num == 0:
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
                
                current_month_year = f"{now.year}{now.month:02d}"
                
                for stream in streams:
                    if stream.recording_path and "S" in stream.recording_path and "E" in stream.recording_path:
                        try:
                            # Extract episode number from path like "S202507E02"
                            import re
                            match = re.search(rf'S{current_month_year}E(\d+)', stream.recording_path)
                            if match:
                                episode_num = int(match.group(1))
                                max_episode_num = max(max_episode_num, episode_num)
                        except (ValueError, AttributeError):
                            continue
                
                # If still no episodes found, also check filesystem for safety
                if max_episode_num == 0:
                    try:
                        from app.config.settings import get_settings
                        settings = get_settings()
                        output_directory = getattr(settings, 'output_directory', '/recordings')
                        
                        # Get streamer name
                        from app.models import Streamer
                        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                        if streamer:
                            streamer_dir = await async_file.join(output_directory, streamer.username)
                            season_dir = await async_file.join(streamer_dir, f"Season {now.year}-{now.month:02d}")
                            
                            if await async_file.exists(season_dir):
                                import re
                                for filename in await async_file.listdir(season_dir):
                                    match = re.search(rf'S{current_month_year}E(\d+)', filename)
                                    if match:
                                        episode_num = int(match.group(1))
                                        max_episode_num = max(max_episode_num, episode_num)
                    except Exception as fs_error:
                        logger.debug(f"Could not check filesystem for episodes: {fs_error}")
            
            # Next episode number
            episode_number = max_episode_num + 1
            
            logger.debug(
                f"Episode number for streamer {streamer_id} in {now.year}-{now.month:02d}: {episode_number} (max existing: {max_episode_num})"
            )
            return f"{episode_number:02d}"  # Format with leading zero

    except Exception as e:
        logger.error(f"Error getting episode number: {e}", exc_info=True)
        return "01"  # Default value

async def generate_filename(
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
    episode_str = await get_episode_number(streamer.id, now)
    episode_int = int(episode_str)  # Convert to int for formatting

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
        "episode": episode_int,  # Episode number as integer for formatting
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
                    try:
                        if fmt.endswith(':02d}') and isinstance(value, str) and value.isdigit():
                            # For numbers as strings with 02d format
                            filename = filename.replace(fmt, f"{int(value):02d}")
                        elif fmt.endswith(':d}') and isinstance(value, str) and value.isdigit():
                            # For numbers as strings with simple d format
                            filename = filename.replace(fmt, f"{int(value)}")
                        elif fmt.endswith(':2d}') and isinstance(value, str) and value.isdigit():
                            # For numbers as strings with 2d format
                            filename = filename.replace(fmt, f"{int(value):2d}")
                        else:
                            # Just replace with string value
                            filename = filename.replace(fmt, str(value))
                    except Exception as format_error:
                        # Last resort, just use the string value
                        logger.warning(f"Format replacement error with {fmt}: {format_error}")
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

async def update_episode_number(stream_id: int, episode_number: int):
    """
    Update the episode number for a stream.
    
    Args:
        stream_id: ID of the stream
        episode_number: Episode number to set
    """
    try:
        from app.models import Stream
        
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if stream:
                # Check if episode_number column exists before trying to set it
                try:
                    stream.episode_number = episode_number
                    db.commit()
                    logger.info(f"Updated episode_number for stream {stream_id}: {episode_number}")
                except Exception as col_error:
                    # If column doesn't exist, log debug message and continue
                    logger.debug(f"Could not set episode_number (column may not exist): {col_error}")
            else:
                logger.warning(f"Stream {stream_id} not found for episode_number update")
    except Exception as e:
        logger.error(f"Error updating episode_number for stream {stream_id}: {e}", exc_info=True)
