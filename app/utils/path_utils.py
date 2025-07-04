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
    
    Args:
        streamer_id: ID of the streamer
        now: Current datetime
        
    Returns:
        Episode number as a two-digit string
    """
    try:
        from app.models import Stream
        
        with SessionLocal() as db:
            # Count streams in the current month for this streamer
            stream_count = (
                db.query(Stream)
                .filter(
                    Stream.streamer_id == streamer_id,
                    extract("year", Stream.started_at) == now.year,
                    extract("month", Stream.started_at) == now.month,
                )
                .count()
            )
            # Add 1 for the current stream
            episode_number = stream_count + 1
            logger.debug(
                f"Episode number for streamer {streamer_id} in {now.year}-{now.month:02d}: {episode_number}"
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
        "season": f"S{now.year}{now.month:02d}",  # Saison ohne Bindestrich
        "episode": f"E{episode}",  # Präfix E zur Episodennummer hinzufügen
    }

    # Check if template is a preset name
    if template in FILENAME_PRESETS:
        template = FILENAME_PRESETS[template]
        
    # Replace all variables in template
    filename = template
    for key, value in values.items():
        placeholder = f"{{{key}}}"
        if placeholder in filename:  # Prüfen, ob der Platzhalter vorhanden ist
            filename = filename.replace(placeholder, str(value))

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
