"""MP4Box utility functions for StreamVault metadata handling."""
import os
import asyncio
import logging
import subprocess
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("streamvault")

class MP4BoxError(Exception):
    """Custom exception for MP4Box operations."""
    pass

class MP4BoxNotAvailableError(MP4BoxError):
    """Exception raised when MP4Box is not available."""
    pass

async def check_mp4box_availability() -> bool:
    """Check if MP4Box is available on the system."""
    try:
        process = await asyncio.create_subprocess_exec(
            "MP4Box", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode == 0
    except FileNotFoundError:
        logger.warning("MP4Box not found - falling back to FFmpeg for metadata operations")
        return False
    except Exception as e:
        logger.error(f"Error checking MP4Box availability: {e}")
        return False

async def validate_mp4_with_mp4box(mp4_path: str) -> bool:
    """
    Validate MP4 file using MP4Box.
    
    Args:
        mp4_path: Path to the MP4 file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if MP4Box is available
        if not await check_mp4box_availability():
            logger.warning("MP4Box not available, cannot validate with MP4Box")
            raise MP4BoxNotAvailableError("MP4Box is not available")
            
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:
            logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
            return False

        # Use MP4Box to validate file structure
        cmd = ["MP4Box", "-info", mp4_path]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.debug(f"MP4 file validation successful: {mp4_path}")
            return True
        else:
            logger.warning(f"MP4 file validation failed: {stderr.decode()}")
            return False
            
    except MP4BoxNotAvailableError:
        raise
    except Exception as e:
        logger.error(f"Error validating MP4 file with MP4Box: {e}")
        return False

async def get_mp4_info(mp4_path: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about MP4 file using MP4Box.
    
    Args:
        mp4_path: Path to the MP4 file
        
    Returns:
        Dictionary with file information or None on error
    """
    try:
        cmd = ["MP4Box", "-info", mp4_path]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            info_text = stdout.decode()
            # Parse the output to extract useful information
            info = _parse_mp4box_info(info_text)
            return info
        else:
            logger.error(f"Failed to get MP4 info: {stderr.decode()}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting MP4 info: {e}")
        return None

def _parse_mp4box_info(info_text: str) -> Dict[str, Any]:
    """Parse MP4Box info output into a structured format."""
    info = {}
    
    lines = info_text.split('\n')
    for line in lines:
        line = line.strip()
        if "Duration" in line:
            # Extract duration
            try:
                duration_str = line.split("Duration")[1].split("(")[0].strip()
                info["duration"] = duration_str
            except:
                pass
        elif "Video" in line and "fps" in line:
            # Extract video info
            info["has_video"] = True
            if "fps" in line:
                try:
                    fps_part = line.split("fps")[0].split()[-1]
                    info["fps"] = float(fps_part)
                except:
                    pass
        elif "Audio" in line and "Hz" in line:
            # Extract audio info
            info["has_audio"] = True
    
    return info

async def embed_metadata_with_mp4box(
    input_path: str, 
    output_path: str, 
    metadata: Dict[str, Any],
    chapters: Optional[List[Dict[str, Any]]] = None
) -> bool:
    """
    Embed metadata into MP4 file using MP4Box.
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output MP4 file
        metadata: Dictionary with metadata to embed
        chapters: Optional list of chapter information
        
    Returns:
        True on success, False on error
    """
    try:
        # Create a temporary copy first
        temp_path = f"{output_path}.tmp"
        
        # Copy file to temp location
        import shutil
        shutil.copy2(input_path, temp_path)
        
        # Add metadata using MP4Box
        success = await _add_metadata_to_mp4(temp_path, metadata)
        
        if success and chapters:
            success = await _add_chapters_to_mp4(temp_path, chapters)
        
        if success:
            # Move temp file to final location
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_path, output_path)
            logger.info(f"Successfully embedded metadata in {output_path}")
            return True
        else:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
            
    except Exception as e:
        logger.error(f"Error embedding metadata with MP4Box: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

async def _add_metadata_to_mp4(mp4_path: str, metadata: Dict[str, Any]) -> bool:
    """Add metadata to MP4 file using MP4Box."""
    try:
        cmd = ["MP4Box"]
        
        # Add various metadata fields
        if metadata.get("title"):
            cmd.extend(["-itags", f"title={metadata['title']}"])
        
        if metadata.get("artist"):
            cmd.extend(["-itags", f"artist={metadata['artist']}"])
        
        if metadata.get("album"):
            cmd.extend(["-itags", f"album={metadata['album']}"])
        
        if metadata.get("year"):
            cmd.extend(["-itags", f"created={metadata['year']}"])
        
        if metadata.get("genre"):
            cmd.extend(["-itags", f"genre={metadata['genre']}"])
        
        if metadata.get("comment"):
            cmd.extend(["-itags", f"comment={metadata['comment']}"])
        
        if metadata.get("description"):
            cmd.extend(["-itags", f"description={metadata['description']}"])
        
        # Add custom metadata
        if metadata.get("streamer"):
            cmd.extend(["-itags", f"albumartist={metadata['streamer']}"])
        
        if metadata.get("game"):
            cmd.extend(["-itags", f"grouping={metadata['game']}"])
        
        if metadata.get("stream_date"):
            cmd.extend(["-itags", f"date={metadata['stream_date']}"])
        
        cmd.append(mp4_path)
        
        # Log the command for debugging
        logger.info(f"MP4Box metadata command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Log both stdout and stderr for debugging
        stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stdout_text:
            logger.info(f"MP4Box stdout: {stdout_text}")
        if stderr_text:
            logger.info(f"MP4Box stderr: {stderr_text}")
        
        if process.returncode == 0:
            logger.info(f"Successfully added metadata to {mp4_path}")
            return True
        else:
            logger.error(f"Failed to add metadata (exit code {process.returncode}): {stderr_text}")
            return False
            
    except Exception as e:
        logger.error(f"Error adding metadata to MP4: {e}")
        return False

async def _add_chapters_to_mp4(mp4_path: str, chapters: List[Dict[str, Any]]) -> bool:
    """Add chapters to MP4 file using MP4Box."""
    try:
        # Create temporary chapter file
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            chapter_file = f.name
            
            # Write chapters in MP4Box format
            for i, chapter in enumerate(chapters):
                start_time = chapter.get('start_time', 0)
                title = chapter.get('title', f'Chapter {i+1}')
                
                # Convert seconds to timecode format (HH:MM:SS.mmm)
                hours = int(start_time // 3600)
                minutes = int((start_time % 3600) // 60)
                seconds = start_time % 60
                
                timecode = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
                f.write(f"CHAPTER{i+1:02d}={timecode}\n")
                f.write(f"CHAPTER{i+1:02d}NAME={title}\n")
        
        # Add chapters using MP4Box
        cmd = ["MP4Box", "-chap", chapter_file, mp4_path]
        
        # Log the command for debugging
        logger.info(f"MP4Box chapter command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Log both stdout and stderr for debugging
        stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stdout_text:
            logger.info(f"MP4Box chapter stdout: {stdout_text}")
        if stderr_text:
            logger.info(f"MP4Box chapter stderr: {stderr_text}")
        
        # Clean up chapter file
        os.unlink(chapter_file)
        
        if process.returncode == 0:
            logger.info(f"Successfully added chapters to {mp4_path}")
            return True
        else:
            logger.error(f"Failed to add chapters (exit code {process.returncode}): {stderr_text}")
            return False
            
    except Exception as e:
        logger.error(f"Error adding chapters to MP4: {e}")
        return False

async def optimize_mp4_with_mp4box(input_path: str, output_path: str) -> bool:
    """
    Optimize MP4 file for streaming using MP4Box.
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output MP4 file
        
    Returns:
        True on success, False on error
    """
    try:
        cmd = [
            "MP4Box",
            "-inter", "500",  # Interleave every 500ms
            "-flat",          # Flatten the file structure
            "-new", output_path,
            input_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Successfully optimized MP4: {output_path}")
            return True
        else:
            logger.error(f"Failed to optimize MP4: {stderr.decode()}")
            return False
            
    except Exception as e:
        logger.error(f"Error optimizing MP4: {e}")
        return False

async def extract_thumbnail_with_mp4box(
    mp4_path: str, 
    output_path: str, 
    time_offset: float = 0
) -> bool:
    """
    Extract thumbnail from MP4 file using MP4Box.
    
    Args:
        mp4_path: Path to MP4 file
        output_path: Path for output thumbnail
        time_offset: Time offset in seconds
        
    Returns:
        True on success, False on error
    """
    try:
        cmd = [
            "MP4Box",
            "-single", "1",  # Extract first video track
            "-out", output_path,
            mp4_path
        ]
        
        # If time offset is specified, add it
        if time_offset > 0:
            cmd.extend(["-start", str(time_offset)])
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.debug(f"Successfully extracted thumbnail: {output_path}")
            return True
        else:
            logger.error(f"Failed to extract thumbnail: {stderr.decode()}")
            return False
            
    except Exception as e:
        logger.error(f"Error extracting thumbnail: {e}")
        return False

async def get_mp4_duration(mp4_path: str) -> Optional[float]:
    """
    Get duration of MP4 file in seconds using MP4Box.
    
    Args:
        mp4_path: Path to MP4 file
        
    Returns:
        Duration in seconds or None on error
    """
    try:
        info = await get_mp4_info(mp4_path)
        if info and "duration" in info:
            duration_str = info["duration"]
            # Parse duration string (format: "00:05:30.123")
            parts = duration_str.split(":")
            if len(parts) >= 3:
                hours = float(parts[0])
                minutes = float(parts[1]) 
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        return None
        
    except Exception as e:
        logger.error(f"Error getting MP4 duration: {e}")
        return None
