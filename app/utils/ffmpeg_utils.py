"""FFmpeg utility functions for StreamVault."""
import os
import asyncio
import logging
import subprocess
from typing import Optional, Dict, Any

# Import MP4Box utilities
from .mp4box_utils import (
    validate_mp4_with_mp4box, 
    embed_metadata_with_mp4box,
    optimize_mp4_with_mp4box,
    get_mp4_duration
)

logger = logging.getLogger("streamvault")

async def validate_mp4(mp4_path: str) -> bool:
    """
    Validate that an MP4 file is properly created and readable.
    Uses MP4Box for better validation.
    
    Args:
        mp4_path: Path to the MP4 file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # First check basic file properties
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:
            logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
            return False

        # Use MP4Box for validation (more reliable than ffprobe for MP4)
        return await validate_mp4_with_mp4box(mp4_path)

    except Exception as e:
        logger.error(f"Error validating MP4 file: {e}", exc_info=True)
        return False

async def create_metadata_file(metadata: dict) -> Optional[str]:
    """
    Create a temporary metadata file for FFmpeg.
    Note: This is kept for compatibility, but MP4Box metadata embedding is preferred.
    
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

async def embed_metadata_in_mp4(
    input_path: str, 
    output_path: str, 
    metadata: Dict[str, Any],
    chapters: Optional[list] = None
) -> bool:
    """
    Embed metadata into MP4 file using MP4Box (preferred method).
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output MP4 file
        metadata: Dictionary with metadata to embed
        chapters: Optional list of chapter information
        
    Returns:
        True on success, False on error
    """
    try:
        logger.info(f"Embedding metadata in {input_path} -> {output_path}")
        
        # Use MP4Box for metadata embedding
        success = await embed_metadata_with_mp4box(
            input_path, 
            output_path, 
            metadata, 
            chapters
        )
        
        if success:
            logger.info(f"Successfully embedded metadata using MP4Box")
            return True
        else:
            logger.error(f"Failed to embed metadata using MP4Box")
            return False
            
    except Exception as e:
        logger.error(f"Error embedding metadata: {e}")
        return False

async def optimize_mp4_for_streaming(input_path: str, output_path: str) -> bool:
    """
    Optimize MP4 file for streaming using MP4Box.
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output MP4 file
        
    Returns:
        True on success, False on error
    """
    try:
        return await optimize_mp4_with_mp4box(input_path, output_path)
    except Exception as e:
        logger.error(f"Error optimizing MP4: {e}")
        return False
