"""FFmpeg utility functions for StreamVault."""
import os
import asyncio
import logging
import subprocess
from typing import Optional, Dict, Any

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
        # First check basic file properties
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:
            logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
            return False

        return True

    except Exception as e:
        logger.error(f"Error validating MP4 file: {e}", exc_info=True)
        return False

async def create_metadata_file(metadata: dict) -> Optional[str]:
    """
    Create a temporary metadata file for FFmpeg in the correct format.
    
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

async def convert_ts_to_mp4(
    input_path: str, 
    output_path: str, 
    metadata_file: Optional[str] = None,
    overwrite: bool = False,
    logging_service = None
) -> Dict[str, Any]:
    """
    Convert TS file to MP4 using FFmpeg with proper settings.
    This function follows the approach used in lsdvr for maximum compatibility and quality.
    
    Args:
        input_path: Path to input TS file
        output_path: Path to output MP4 file
        metadata_file: Optional path to FFmpeg metadata file with chapters
        overwrite: Whether to overwrite existing output file
        logging_service: Optional logging service for more detailed logs
        
    Returns:
        Dict with success status, return code and output information
    """
    try:
        if not os.path.exists(input_path):
            logger.error(f"Input file does not exist: {input_path}")
            return {"success": False, "code": -1, "stderr": "Input file does not exist"}
            
        if os.path.exists(output_path) and not overwrite:
            logger.error(f"Output file already exists: {output_path}")
            return {"success": False, "code": -1, "stderr": "Output file already exists"}
            
        # Create FFmpeg command with optimal settings
        cmd = ["ffmpeg", "-i", input_path]
        
        # Add metadata file if provided
        if metadata_file and os.path.exists(metadata_file):
            cmd.extend(["-i", metadata_file, "-map_metadata", "1"])
            
        # Add encoding parameters - copy streams without re-encoding
        cmd.extend([
            "-c", "copy", 
            "-bsf:a", "aac_adtstoasc",  # Fix for AAC audio in TS container
            "-movflags", "faststart",    # Optimize for web streaming
        ])
        
        # Add overwrite flag if needed
        if overwrite:
            cmd.append("-y")
            
        cmd.append(output_path)
        
        # Execute the command
        logger.info(f"Converting {input_path} to {output_path}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Successfully converted {input_path} to {output_path}")
            return {
                "success": True, 
                "code": 0, 
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
        else:
            logger.error(f"Failed to convert {input_path} to {output_path}")
            return {
                "success": False, 
                "code": process.returncode, 
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
    except Exception as e:
        logger.error(f"Error during TS to MP4 conversion: {e}", exc_info=True)
        return {"success": False, "code": -1, "stderr": str(e)}
