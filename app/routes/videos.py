from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, FileResponse
import os
import urllib.parse
from typing import List
import logging
from pathlib import Path
import mimetypes
from app.database import SessionLocal
from app.models import RecordingSettings

logger = logging.getLogger(__name__)
router = APIRouter()

def get_recordings_directory():
    """Get the recordings directory from database settings"""
    with SessionLocal() as db:
        settings = db.query(RecordingSettings).first()
        if settings and settings.output_directory:
            return settings.output_directory
        else:
            # Fallback to default directory
            return "/recordings"

@router.get("/videos")
async def get_all_videos():
    """Get all available videos from all streamers"""
    try:
        videos = []
        recordings_dir = get_recordings_directory()
        
        # Convert to absolute path for local development
        if not os.path.isabs(recordings_dir):
            recordings_dir = os.path.abspath(recordings_dir)
        
        logger.info(f"Looking for videos in directory: {recordings_dir}")
        
        if not os.path.exists(recordings_dir):
            logger.warning(f"Recordings directory {recordings_dir} does not exist")
            return videos
          # Iterate through streamer directories
        for streamer_name in os.listdir(recordings_dir):
            # Validate streamer directory name
            if ".." in streamer_name or "/" in streamer_name or "\\" in streamer_name:
                logger.warning(f"Skipping potentially dangerous streamer directory: {streamer_name}")
                continue
            
            # Additional validation: ensure streamer name contains only safe characters
            import re
            if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_name):
                logger.warning(f"Skipping streamer name with invalid characters: {streamer_name}")
                continue
            
            from pathlib import Path
            base_path = Path(recordings_dir)
            streamer_path = base_path / streamer_name
            
            try:
                resolved_streamer_path = streamer_path.resolve()
                resolved_base_path = base_path.resolve()
                if not str(resolved_streamer_path).startswith(str(resolved_base_path)):
                    logger.warning(f"Skipping streamer directory outside base: {streamer_path}")
                    continue
            except Exception:
                logger.warning(f"Failed to resolve streamer path: {streamer_path}")
                continue
            
            if not resolved_streamer_path.is_dir():
                continue
                
            # Look for video files in streamer directory
            for filename in os.listdir(resolved_streamer_path):
                # Validate filename
                if ".." in filename or "/" in filename or "\\" in filename:
                    logger.warning(f"Skipping potentially dangerous filename: {filename}")
                    continue
                
                if not re.match(r'^[a-zA-Z0-9\-_. ]+$', filename):
                    logger.warning(f"Skipping filename with invalid characters: {filename}")
                    continue
                
                file_path = resolved_streamer_path / filename
                
                # Check if it's a video file                if is_video_file(filename) and file_path.is_file():
                    try:
                        file_stats = file_path.stat()
                        video_info = {
                            "title": filename,
                            "streamer_name": streamer_name,
                            "file_path": str(file_path),  # Use validated path
                            "file_size": file_stats.st_size,
                            "created_at": file_stats.st_mtime,
                            "duration": None,  # Could be extracted with ffprobe if needed
                            "thumbnail_url": None  # Could be generated if needed
                        }
                        
                        videos.append(video_info)
                        
                    except Exception as e:
                        logger.error(f"Error processing video file {file_path}: {e}")
                        continue
        
        # Sort by creation time (newest first)
        videos.sort(key=lambda x: x["created_at"], reverse=True)
        
        logger.info(f"Found {len(videos)} videos")
        return videos
        
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving videos: {str(e)}")

@router.get("/videos/stream/{streamer_name}/{filename}")
async def stream_video(streamer_name: str, filename: str, request: Request):
    """Stream a video file with proper URL decoding and range support"""
    try:
        # Sanitize inputs - no path traversal characters allowed
        if ".." in streamer_name or "/" in streamer_name or "\\" in streamer_name:
            logger.warning(f"Invalid streamer name detected: {streamer_name}")
            raise HTTPException(status_code=400, detail="Invalid streamer name")
        
        # URL decode the filename and sanitize        decoded_filename = urllib.parse.unquote(filename)
        if ".." in decoded_filename or "/" in decoded_filename or "\\" in decoded_filename:
            logger.warning(f"Invalid filename detected: {decoded_filename}")
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Additional validation: ensure filename contains only safe characters
        import re
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', decoded_filename):
            logger.warning(f"Filename contains invalid characters: {decoded_filename}")
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Validate streamer name 
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_name):
            logger.warning(f"Streamer name contains invalid characters: {streamer_name}")
            raise HTTPException(status_code=400, detail="Invalid streamer name")
            
        logger.info(f"Streaming video: {streamer_name}/{decoded_filename}")
        
        # Get recordings directory
        recordings_dir = get_recordings_directory()
        if not os.path.isabs(recordings_dir):
            recordings_dir = os.path.abspath(recordings_dir)
        
        # Construct safe path using only validated components
        from pathlib import Path
        base_path = Path(recordings_dir)
        safe_path = base_path / streamer_name / decoded_filename        
        # Security check - resolve and ensure path is within recordings directory
        try:
            resolved_file_path = safe_path.resolve()
            resolved_recordings_dir = base_path.resolve()
        except Exception as e:
            logger.warning(f"Path resolution failed for {safe_path}: {e}")
            raise HTTPException(status_code=403, detail="Invalid path")
            
        # Security check: ensure resolved path is within recordings directory
        if not str(resolved_file_path).startswith(str(resolved_recordings_dir)):
            logger.warning(f"Attempted path traversal: {safe_path} -> {resolved_file_path}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Additional security check - ensure no symlink attacks on resolved path
        if os.path.islink(resolved_file_path):
            logger.warning(f"Attempted symlink access: {resolved_file_path}")
            raise HTTPException(status_code=403, detail="Symlink access denied")
        
        # Check if file exists (use resolved path)
        if not os.path.exists(resolved_file_path):
            logger.error(f"Video file not found: {resolved_file_path}")
            raise HTTPException(status_code=404, detail="Video file not found")
          # Get file stats (use resolved path)
        file_size = os.path.getsize(resolved_file_path)
        
        # Get MIME type (use resolved path)
        mime_type, _ = mimetypes.guess_type(resolved_file_path)
        if not mime_type:
            mime_type = "video/mp4"  # Default to mp4
        
        # Handle range requests for video streaming
        range_header = request.headers.get("range")
        
        if range_header:
            # Parse range header
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else file_size - 1
            end = min(end, file_size - 1)
              # Create streaming response for range (use resolved path)
            def generate_chunk():
                with open(resolved_file_path, "rb") as f:
                    f.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk_size = min(8192, remaining)  # 8KB chunks
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
                "Content-Type": mime_type,
            }
            
            return StreamingResponse(
                generate_chunk(),
                status_code=206,
                headers=headers
            )        else:
            # Return full file (use resolved path)
            return FileResponse(
                resolved_file_path,
                media_type=mime_type,
                filename=decoded_filename
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {streamer_name}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error streaming video: {str(e)}")

@router.get("/videos/{streamer_name}")
async def get_streamer_videos(streamer_name: str):
    """Get all videos for a specific streamer"""    try:
        # Sanitize streamer_name - no path traversal characters allowed
        if ".." in streamer_name or "/" in streamer_name or "\\" in streamer_name:
            logger.warning(f"Invalid streamer name detected: {streamer_name}")
            raise HTTPException(status_code=400, detail="Invalid streamer name")
        
        # Additional validation: ensure streamer name contains only safe characters
        import re
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_name):
            logger.warning(f"Streamer name contains invalid characters: {streamer_name}")
            raise HTTPException(status_code=400, detail="Invalid streamer name")
            
        videos = []
        recordings_dir = get_recordings_directory()
        if not os.path.isabs(recordings_dir):
            recordings_dir = os.path.abspath(recordings_dir)
        
        # Construct safe path using validated components
        from pathlib import Path
        base_path = Path(recordings_dir)
        streamer_path = base_path / streamer_name
        
        # Security check - ensure path is within recordings directory
        try:
            abs_streamer_path = streamer_path.resolve()
            abs_recordings_dir = base_path.resolve()
            if not str(abs_streamer_path).startswith(str(abs_recordings_dir)):
                logger.warning(f"Attempted path traversal in get_streamer_videos: {streamer_path}")
                raise HTTPException(status_code=403, detail="Access denied")
        except Exception as e:
            logger.warning(f"Path resolution failed for {streamer_path}: {e}")
            raise HTTPException(status_code=403, detail="Invalid path")
        
        if not abs_streamer_path.exists():
            logger.warning(f"Streamer directory {abs_streamer_path} does not exist")
            return videos
        
        for filename in os.listdir(abs_streamer_path):
            # Sanitize filename
            if ".." in filename or "/" in filename or "\\" in filename:
                logger.warning(f"Skipping potentially dangerous filename: {filename}")
                continue
            
            # Additional validation for filename
            if not re.match(r'^[a-zA-Z0-9\-_. ]+$', filename):
                logger.warning(f"Skipping filename with invalid characters: {filename}")
                continue
                  file_path = abs_streamer_path / filename
            
            # Additional security check for each file
            try:
                abs_file_path = file_path.resolve()
                if not str(abs_file_path).startswith(str(abs_streamer_path)):
                    logger.warning(f"Skipping file outside streamer directory: {file_path}")
                    continue
            except Exception:
                logger.warning(f"Failed to resolve file path: {file_path}")
                continue
            
            if is_video_file(filename) and abs_file_path.is_file():
                try:
                    file_stats = abs_file_path.stat()
                      video_info = {
                        "title": filename,
                        "streamer_name": streamer_name,
                        "file_path": str(abs_file_path),  # Use the validated path
                        "file_size": file_stats.st_size,
                        "created_at": file_stats.st_mtime,
                        "duration": None,
                        "thumbnail_url": None
                    }
                      videos.append(video_info)
                    
                except Exception as e:
                    logger.error(f"Error processing video file {abs_file_path}: {e}")
                    continue
        
        # Sort by creation time (newest first)
        videos.sort(key=lambda x: x["created_at"], reverse=True)
        
        return videos
        
    except Exception as e:
        logger.error(f"Error getting videos for streamer {streamer_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving videos: {str(e)}")

def is_video_file(filename: str) -> bool:
    """Check if file is a video file based on extension"""
    video_extensions = {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', 
        '.webm', '.m4v', '.3gp', '.3g2', '.ts', '.m2ts'
    }
    
    return Path(filename).suffix.lower() in video_extensions
