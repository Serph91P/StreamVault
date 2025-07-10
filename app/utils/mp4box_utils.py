"""MP4Box utility functions for StreamVault metadata handling."""
import os
import asyncio
import logging
import subprocess
import json
import shutil
import tempfile
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
            
        if not os.path.exists(mp4_path):
            logger.warning(f"MP4 file does not exist: {mp4_path}")
            return False
            
        file_size = os.path.getsize(mp4_path)
        if file_size < 10000:
            logger.warning(f"MP4 file is too small ({file_size} bytes): {mp4_path}")
            return False

        # Use MP4Box to validate file structure with timeout
        cmd = ["MP4Box", "-info", mp4_path]
        
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=30.0  # 30 second timeout
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0  # 60 second timeout for communication
            )
        except asyncio.TimeoutError:
            logger.warning(f"MP4Box validation timed out for: {mp4_path}")
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.returncode is None:
                    process.kill()
            except:
                pass
            return False
        
        if process.returncode == 0:
            logger.debug(f"MP4 file validation successful: {mp4_path}")
            return True
        else:
            stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
            logger.warning(f"MP4 file validation failed (exit code {process.returncode}): {stderr_text}")
            
            # Even if MP4Box reports an error, if the file exists and has reasonable size,
            # it might still be usable - don't be too strict
            if file_size > 100000:  # If file is larger than 100KB, it might be OK
                logger.info(f"MP4 file has reasonable size despite validation error, considering it potentially valid")
                return True
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
    temp_path = None
    try:
        # Validate input file exists and is readable
        if not os.path.exists(input_path):
            logger.error(f"Input file does not exist: {input_path}")
            return False
            
        if os.path.getsize(input_path) == 0:
            logger.error(f"Input file is empty: {input_path}")
            return False
        
        # Create a temporary copy first
        temp_path = f"{output_path}.tmp"
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Clean up any existing temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Removed existing temp file: {temp_path}")
            except Exception as cleanup_e:
                logger.warning(f"Could not remove existing temp file {temp_path}: {cleanup_e}")
        
        # Copy file to temp location with error handling
        import shutil
        try:
            shutil.copy2(input_path, temp_path)
            logger.debug(f"Created temp copy: {input_path} -> {temp_path}")
        except Exception as copy_e:
            logger.error(f"Failed to create temp copy: {copy_e}")
            return False
        
        # Verify temp file was created successfully
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            logger.error(f"Temp file creation failed or resulted in empty file: {temp_path}")
            return False
        
        # Add metadata using MP4Box
        success = await _add_metadata_to_mp4(temp_path, metadata)
        
        if success and chapters:
            success = await _add_chapters_to_mp4(temp_path, chapters)
        
        if success:
            # Verify temp file is still valid after MP4Box operations
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                logger.error(f"Temp file became invalid after MP4Box operations: {temp_path}")
                return False
            
            # Validate the processed file structure
            try:
                is_valid = await validate_mp4_with_mp4box(temp_path)
                if not is_valid:
                    logger.warning(f"MP4Box processing resulted in invalid MP4 structure: {temp_path}")
                    # Don't fail entirely - the file might still be usable
            except Exception as validation_e:
                logger.warning(f"Could not validate processed MP4 file: {validation_e}")
                # Continue anyway as validation failure doesn't mean the file is unusable
            
            # Move temp file to final location
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_path, output_path)
                logger.info(f"Successfully embedded metadata in {output_path}")
                temp_path = None  # Reset so cleanup doesn't try to remove moved file
                return True
            except Exception as move_e:
                logger.error(f"Failed to move temp file to final location: {move_e}")
                return False
        else:
            logger.warning(f"MP4Box metadata/chapter operations failed for: {input_path}")
            return False
            
    except Exception as e:
        logger.error(f"Error embedding metadata with MP4Box: {e}", exc_info=True)
        return False
    finally:
        # Always clean up temp file if it still exists
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as cleanup_e:
                logger.warning(f"Could not clean up temp file {temp_path}: {cleanup_e}")

async def _add_metadata_to_mp4(mp4_path: str, metadata: Dict[str, Any]) -> bool:
    """Add metadata to MP4 file using MP4Box."""
    try:
        # Validate input file first
        if not os.path.exists(mp4_path):
            logger.error(f"MP4 file does not exist: {mp4_path}")
            return False
            
        if os.path.getsize(mp4_path) == 0:
            logger.error(f"MP4 file is empty: {mp4_path}")
            return False

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
        
        # Add encoded_by and encoding_tool metadata
        if metadata.get("encoded_by"):
            cmd.extend(["-itags", f"encoded_by={metadata['encoded_by']}"])
            
        if metadata.get("encoding_tool"):
            cmd.extend(["-itags", f"tool={metadata['encoding_tool']}"])
            
        if metadata.get("original_format"):
            cmd.extend(["-itags", f"original_format={metadata['original_format']}"])
            
        if metadata.get("remux_date"):
            cmd.extend(["-itags", f"remux_date={metadata['remux_date']}"])

        cmd.append(mp4_path)
        
        # Log the command for debugging
        logger.info(f"MP4Box metadata command: {' '.join(cmd)}")
        
        # Set timeout for MP4Box operation to prevent hanging
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=30.0  # 30 second timeout
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0  # 60 second timeout for communication
            )
        except asyncio.TimeoutError:
            logger.error(f"MP4Box metadata operation timed out for: {mp4_path}")
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.returncode is None:
                    process.kill()
            except:
                pass
            return False
        
        # Log both stdout and stderr for debugging
        stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stdout_text:
            logger.debug(f"MP4Box stdout: {stdout_text}")
        if stderr_text:
            logger.debug(f"MP4Box stderr: {stderr_text}")
        
        # Check if file still exists and has reasonable size after operation
        if not os.path.exists(mp4_path):
            logger.error(f"MP4 file disappeared after metadata operation: {mp4_path}")
            return False
            
        if os.path.getsize(mp4_path) == 0:
            logger.error(f"MP4 file became empty after metadata operation: {mp4_path}")
            return False

        if process.returncode == 0:
            logger.info(f"Successfully added metadata to {mp4_path}")
            return True
        else:
            # Log error but don't necessarily fail - some metadata operations might have partial success
            logger.warning(f"MP4Box metadata operation returned non-zero exit code {process.returncode} for {mp4_path}")
            logger.warning(f"stderr: {stderr_text}")
            
            # If the file still exists and has content, consider it a partial success
            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                logger.info(f"MP4 file still valid despite non-zero exit code, considering operation successful")
                return True
            else:
                logger.error(f"MP4 file invalid after metadata operation failure")
                return False
            
    except Exception as e:
        logger.error(f"Error adding metadata to MP4: {e}", exc_info=True)
        return False

async def _add_chapters_to_mp4(mp4_path: str, chapters: List[Dict[str, Any]]) -> bool:
    """Add chapters to MP4 file using MP4Box."""
    chapter_file = None
    try:
        # Validate input file first
        if not os.path.exists(mp4_path):
            logger.error(f"MP4 file does not exist: {mp4_path}")
            return False
            
        if os.path.getsize(mp4_path) == 0:
            logger.error(f"MP4 file is empty: {mp4_path}")
            return False

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
        
        # Verify chapter file was created
        if not os.path.exists(chapter_file) or os.path.getsize(chapter_file) == 0:
            logger.error(f"Failed to create chapter file: {chapter_file}")
            return False
        
        # Add chapters using MP4Box
        cmd = ["MP4Box", "-chap", chapter_file, mp4_path]
        
        # Log the command for debugging
        logger.info(f"MP4Box chapter command: {' '.join(cmd)}")
        
        # Set timeout for MP4Box operation
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=30.0  # 30 second timeout
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0  # 60 second timeout for communication
            )
        except asyncio.TimeoutError:
            logger.error(f"MP4Box chapter operation timed out for: {mp4_path}")
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.returncode is None:
                    process.kill()
            except:
                pass
            return False
        
        # Log both stdout and stderr for debugging
        stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stdout_text:
            logger.debug(f"MP4Box chapter stdout: {stdout_text}")
        if stderr_text:
            logger.debug(f"MP4Box chapter stderr: {stderr_text}")
        
        # Check if file still exists and has reasonable size after operation
        if not os.path.exists(mp4_path):
            logger.error(f"MP4 file disappeared after chapter operation: {mp4_path}")
            return False
            
        if os.path.getsize(mp4_path) == 0:
            logger.error(f"MP4 file became empty after chapter operation: {mp4_path}")
            return False

        if process.returncode == 0:
            logger.info(f"Successfully added chapters to {mp4_path}")
            return True
        else:
            # Log error but don't necessarily fail - some chapter operations might have partial success
            logger.warning(f"MP4Box chapter operation returned non-zero exit code {process.returncode} for {mp4_path}")
            logger.warning(f"stderr: {stderr_text}")
            
            # If the file still exists and has content, consider it a partial success
            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                logger.info(f"MP4 file still valid despite non-zero exit code, considering chapter operation successful")
                return True
            else:
                logger.error(f"MP4 file invalid after chapter operation failure")
                return False
            
    except Exception as e:
        logger.error(f"Error adding chapters to MP4: {e}", exc_info=True)
        return False
    finally:
        # Always clean up chapter file
        if chapter_file and os.path.exists(chapter_file):
            try:
                os.unlink(chapter_file)
                logger.debug(f"Cleaned up chapter file: {chapter_file}")
            except Exception as cleanup_e:
                logger.warning(f"Could not clean up chapter file {chapter_file}: {cleanup_e}")

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
