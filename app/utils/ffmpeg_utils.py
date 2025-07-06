"""FFmpeg utility functions for StreamVault."""
import os
import asyncio
import logging
import subprocess
from typing import Optional

logger = logging.getLogger("streamvault")

async def validate_mp4(mp4_path: str) -> bool:
    """
    Validate that an MP4 file is properly created and readable.
    
    Args:
        mp4_path: Path to the MP4 file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if file exists and has reasonable size
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:
            logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
            return False

        # Simple validation: Can ffprobe read the file and get basic info?
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_format",
            "-show_streams",
            mp4_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        # If ffprobe can read the file successfully, it's valid
        if process.returncode == 0 and stdout:
            logger.debug(f"MP4 file validation: File is readable and valid")
            return True
        else:
            logger.warning(f"MP4 file validation failed: ffprobe returned {process.returncode}")
            return False

    except Exception as e:
        logger.error(f"Error validating MP4 file: {e}", exc_info=True)
        return False

async def create_metadata_file(metadata: dict) -> Optional[str]:
    """
    Create a temporary metadata file for FFmpeg.
    
    Args:
        metadata: Dictionary with metadata key-value pairs
        
    Returns:
        Path to the metadata file or None if creation failed
    """
    try:
        import tempfile
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8') as f:
            meta_path = f.name
            f.write(";FFMETADATA1\n")
            for key, value in metadata.items():
                if value:  # Only write if a value exists
                    # Escape special characters
                    value_escaped = str(value).replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\\", "\\\\")
                    f.write(f"{key}={value_escaped}\n")
        
        return meta_path
    except Exception as e:
        logger.error(f"Failed to create metadata file: {e}")
        return None
