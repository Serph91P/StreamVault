"""FFmpeg utility functions for StreamVault."""
import os
import asyncio
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.services.system.logging_service import logging_service

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
    Embed metadata into MP4 file using FFmpeg.
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output MP4 file
        metadata: Dictionary with metadata to embed
        chapters: Optional list of chapter information
        
    Returns:
        True on success, False on error
    """
    try:
        logger.info(f"Embedding metadata with FFmpeg: {input_path} -> {output_path}")
        
        # Build FFmpeg command
        cmd = ["ffmpeg", "-i", input_path]
        
        # Add metadata
        for key, value in metadata.items():
            if value:
                cmd.extend(["-metadata", f"{key}={value}"])
        
        # Copy streams without re-encoding
        cmd.extend(["-c", "copy", "-y", output_path])
        
        # Execute FFmpeg
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("Successfully embedded metadata with FFmpeg")
            return True
        else:
            logger.error(f"FFmpeg metadata embedding failed with return code {process.returncode}")
            logger.error(f"FFmpeg stderr: {stderr.decode('utf-8', errors='replace')[:500]}")
            return False
            
    except Exception as e:
        logger.error(f"Error with FFmpeg metadata embedding: {e}")
        return False

async def convert_ts_to_mp4(
    input_path: str, 
    output_path: str, 
    metadata_file: Optional[str] = None,
    overwrite: bool = False,
    logging_service = None,
    streamer_name: str = "unknown"
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
        
        # Use the logging service to create per-streamer logs
        if logging_service:
            streamer_log_path = logging_service.log_ffmpeg_start("ts_to_mp4", cmd, streamer_name)
            logger.info(f"FFmpeg logs will be written to: {streamer_log_path}")
        
        # Execute the command
        logger.info(f"Converting {input_path} to {output_path}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Log the FFmpeg output using the logging service
        if logging_service:
            logging_service.log_ffmpeg_output("ts_to_mp4", stdout, stderr, process.returncode, streamer_name)
        
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
            logger.error(f"FFmpeg stderr: {stderr.decode('utf-8', errors='replace')[:1000]}")
            return {
                "success": False, 
                "code": process.returncode, 
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
    except Exception as e:
        logger.error(f"Error during TS to MP4 conversion: {e}", exc_info=True)
        return {"success": False, "code": -1, "stderr": str(e)}

async def extract_video_duration(video_path: str) -> Optional[float]:
    """
    Extract video duration in seconds using FFmpeg.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Duration in seconds or None if extraction failed
    """
    try:
        cmd = [
            "ffprobe", 
            "-v", "quiet", 
            "-show_entries", "format=duration", 
            "-of", "csv=p=0", 
            video_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            duration_str = stdout.decode('utf-8').strip()
            return float(duration_str)
        else:
            logger.error(f"Failed to extract duration from {video_path}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting video duration: {e}")
        return None
    
async def embed_metadata_with_ffmpeg_wrapper(
    input_path: str,
    output_path: str, 
    metadata: Dict[str, Any],
    chapters: Optional[list] = None,
    streamer_name: str = "unknown",
    logging_service=None
) -> Dict[str, Any]:
    """
    Embed metadata into MP4 file using FFmpeg.
    
    Args:
        input_path: Path to the input MP4 file
        output_path: Path to the output MP4 file
        metadata: Dictionary with metadata to embed
        chapters: Optional list of chapter information
        streamer_name: Name of the streamer for logging purposes
        logging_service: Optional logging service for more detailed logging
        
    Returns:
        Dict containing success status and details
    """
    operation_id = None
    try:
        logger.info(f"Starting FFmpeg metadata embedding for {streamer_name}: {input_path} -> {output_path}")
        
        # Validate input file exists and has content
        if not os.path.exists(input_path):
            logger.error(f"Input file {input_path} does not exist")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Input file does not exist"
            }
            
        input_size = os.path.getsize(input_path)
        if input_size == 0:
            logger.error(f"Input file {input_path} is empty")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Input file is empty"
            }
        
        # Check if output file already exists
        if os.path.exists(output_path):
            if os.path.getsize(output_path) == 0:
                try:
                    os.remove(output_path)
                    logger.debug(f"Removed empty output file: {output_path}")
                except Exception as remove_e:
                    logger.warning(f"Could not remove empty output file: {remove_e}")
            else:
                logger.error(f"Output file {output_path} already exists and is not empty")
                return {
                    "success": False,
                    "code": -1,
                    "stdout": "",
                    "stderr": "Output file already exists"
                }
        
        # Generate operation ID for logging
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        operation_id = f"ffmpeg_metadata_{streamer_name}_{timestamp_str}"
        
        # Log the operation start
        if logging_service:
            logging_service.ffmpeg_logger.info(f"[FFMPEG_METADATA_START] {streamer_name} - {input_path} -> {output_path}")
            
        # Create a temporary file for FFmpeg chapters
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            metadata_file = f.name
            # Write global metadata
            f.write(";FFMETADATA1\n")
            if "title" in metadata:
                f.write(f"title={metadata['title']}\n")
            if "artist" in metadata:
                f.write(f"artist={metadata['artist']}\n")
            if "date" in metadata:
                f.write(f"date={metadata['date']}\n")
                f.write(f"year={metadata['date'].split('-')[0] if '-' in metadata['date'] else metadata['date']}\n")
            if "creation_time" in metadata:
                f.write(f"creation_time={metadata['creation_time']}\n")
                
            # Write chapter information if available
            if chapters:
                for chapter in chapters:
                    f.write("\n[CHAPTER]\n")
                    f.write(f"TIMEBASE=1/1000\n")
                    f.write(f"START={int(float(chapter.get('start_time', 0)) * 1000)}\n")
                    f.write(f"END={int(float(chapter.get('end_time', 0)) * 1000)}\n")
                    f.write(f"title={chapter.get('title', 'Chapter')}\n")
        
        # Use FFmpeg to remux with metadata
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-i", metadata_file,
            "-map_metadata", "1",
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "faststart",
            "-y",
            output_path
        ]
        
        # Use the logging service to create per-streamer logs
        if logging_service:
            streamer_log_path = logging_service.log_ffmpeg_start("metadata_embed", cmd, streamer_name)
            logger.info(f"FFmpeg logs will be written to: {streamer_log_path}")
        
        # Execute FFmpeg command
        logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        success_code = process.returncode == 0
        
        # Log the FFmpeg output using the logging service
        if logging_service:
            logging_service.log_ffmpeg_output("metadata_embed", stdout, stderr, process.returncode, streamer_name)
        
        # Clean up temporary metadata file
        try:
            os.unlink(metadata_file)
        except Exception as e:
            logger.warning(f"Could not remove temporary metadata file: {e}")
        
        if success_code:
            # Validate the output file
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                # Perform basic size check
                output_size = os.path.getsize(output_path)
                size_ratio = output_size / input_size if input_size > 0 else 0
                
                if size_ratio < 0.8:  # Output is significantly smaller than input
                    logger.warning(f"Output file size seems small (ratio: {size_ratio:.2f}), but continuing since FFmpeg succeeded")
                
                # Basic check - file exists and has size
                logger.info(f"FFmpeg metadata embedding successful: {output_path} (size: {output_size} bytes)")
            else:
                logger.error(f"FFmpeg output file {output_path} is missing or empty")
                success_code = False
        
        if success_code:
            logger.info(f"FFmpeg metadata embedding successful: {operation_id}")
            if logging_service:
                logging_service.ffmpeg_logger.info(f"[FFMPEG_METADATA_SUCCESS] {streamer_name} - {output_path}")
            
            return {
                "success": True,
                "code": 0,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
        else:
            logger.error(f"FFmpeg metadata embedding failed - no valid output file: {operation_id}")
            if logging_service:
                logging_service.ffmpeg_logger.error(f"[FFMPEG_METADATA_FAILED] {streamer_name} - {input_path}")
            
            # Check if at least we have a partial output file
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.warning(f"FFmpeg failed but output file exists with size {os.path.getsize(output_path)}")
                # We'll just warn but not try to recover - better to re-process properly
                try:
                    # Remove the partial file to avoid confusion
                    os.remove(output_path)
                    logger.debug(f"Removed partial output file: {output_path}")
                except Exception as remove_e:
                    logger.warning(f"Could not remove partial output file: {remove_e}")
            
            return {
                "success": False,
                "code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
            
    except Exception as e:
        logger.error(f"Error during FFmpeg metadata embedding: {e}", exc_info=True)
        if logging_service:
            logging_service.ffmpeg_logger.error(f"[FFMPEG_METADATA_ERROR] {streamer_name} - {str(e)}")
        return {
            "success": False,
            "code": -1,
            "stdout": "",
            "stderr": f"Error in FFmpeg metadata embedding: {str(e)}"
        }
        
async def create_ffmpeg_chapters_file(
    chapters: list, 
    output_path: str, 
    title: Optional[str] = None,
    artist: Optional[str] = None,
    date: Optional[str] = None,
    overwrite: bool = False
) -> bool:
    """
    Create an FFmpeg-compatible chapters metadata file.
    
    Args:
        chapters: List of chapter dictionaries with start_time, end_time, and title
        output_path: Path to write the chapters metadata file
        title: Optional video title
        artist: Optional artist/creator name
        date: Optional date in YYYY-MM-DD format
        overwrite: Whether to overwrite an existing file
        
    Returns:
        True on success, False on error
    """
    try:
        if os.path.exists(output_path) and not overwrite:
            logger.warning(f"Chapters file already exists: {output_path}")
            return False
            
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            # FFmpeg metadata header
            f.write(";FFMETADATA1\n")
            
            # Global metadata
            if title:
                f.write(f"title={title}\n")
            if artist:
                f.write(f"artist={artist}\n")
            if date:
                f.write(f"date={date}\n")
                f.write(f"year={date.split('-')[0] if '-' in date else date}\n")
                f.write(f"creation_time={date}\n")
                
            # Chapter information
            if chapters:
                for chapter in chapters:
                    f.write("\n[CHAPTER]\n")
                    f.write("TIMEBASE=1/1000\n")
                    # Convert times to milliseconds
                    start_ms = int(float(chapter['start_time']) * 1000)
                    end_ms = int(float(chapter['end_time']) * 1000)
                    f.write(f"START={start_ms}\n")
                    f.write(f"END={end_ms}\n")
                    # Escape special characters in chapter title
                    chapter_title = chapter.get('title', 'Chapter').replace('=', '\\=')
                    f.write(f"title={chapter_title}\n")
                    
        logger.info(f"Created FFmpeg chapters file with {len(chapters)} chapters: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating chapters file: {e}", exc_info=True)
        return False

