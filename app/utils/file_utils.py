"""File utility functions for StreamVault - ONLY file operations, no metadata!"""
import os
import re
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("streamvault")

def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use as a filename"""
    if not name:
        return "unknown"
    
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
    
    # Collapse multiple spaces/underscores
    name = re.sub(r'[_\s]+', '_', name)
    
    # Remove leading/trailing dots and spaces
    name = name.strip('. ')
    
    # Limit length
    if len(name) > 200:
        name = name[:197] + "..."
    
    return name or "unknown"

async def cleanup_temporary_files(base_path: str):
    """Clean up temporary files after processing"""
    try:
        temp_extensions = ['.tmp', '.part', '.temp']
        base = Path(base_path).parent if base_path else Path('.')
        
        for ext in temp_extensions:
            for temp_file in base.glob(f"*{ext}"):
                try:
                    temp_file.unlink()
                    logger.debug(f"Removed temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Could not remove {temp_file}: {e}")
                    
    except Exception as e:
        logger.error(f"Error cleaning temporary files: {e}")



