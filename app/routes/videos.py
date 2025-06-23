from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, FileResponse
import os
import urllib.parse
from typing import List
import logging
from pathlib import Path
import mimetypes
import re
from app.database import SessionLocal
from app.models import RecordingSettings
from app.utils.security_enhanced import safe_file_access, safe_error_message, list_safe_directory

logger = logging.getLogger(__name__)
router = APIRouter()

def get_recordings_directory():
    """Get the recordings directory from database settings"""
    with SessionLocal() as db:
        settings = db.query(RecordingSettings).first()
        if settings and settings.output_directory:
            return settings.output_directory
        return "/app/recordings"  # fallback

def is_video_file(filename: str) -> bool:
    """Check if a file is a video file based on its extension"""
    video_extensions = {'.mp4', '.avi', '.mkv', '.flv', '.ts', '.m4v', '.webm', '.mov'}
    return Path(filename).suffix.lower() in video_extensions

@router.get("/videos")
async def get_videos():
    """Get all videos from all streamers - CodeQL-safe implementation"""
    videos = []
    
    try:
        recordings_dir = get_recordings_directory()
        if not recordings_dir:
            logger.warning("No recordings directory configured")
            return videos
        
        if not Path(recordings_dir).exists():
            logger.warning(f"Recordings directory {recordings_dir} does not exist")
            return videos
        
        # Get list of streamer directories safely
        try:
            streamer_dirs = list_safe_directory(recordings_dir)
        except HTTPException:
            logger.warning("Failed to list recordings directory")
            return videos
        
        # Process each streamer directory
        for streamer_name in streamer_dirs:
            # Additional validation for streamer name
            if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_name):
                continue
            
            try:
                # Get streamer directory path safely (no user data in path operations)
                streamer_path = safe_file_access(recordings_dir, streamer_name)
                
                if not streamer_path.is_dir():
                    continue
                
                # List files in streamer directory safely
                try:
                    filenames = list_safe_directory(recordings_dir, streamer_name)
                except HTTPException:
                    continue
                
                # Process each video file
                for filename in filenames:
                    if not is_video_file(filename):
                        continue
                    
                    try:
                        # Get file path safely (no user data in path operations)
                        file_path = safe_file_access(recordings_dir, streamer_name, filename)
                        
                        if file_path.is_file():
                            file_stats = file_path.stat()
                            video_info = {
                                "title": filename,
                                "streamer_name": streamer_name,
                                "file_path": str(file_path),
                                "file_size": file_stats.st_size,
                                "created_at": file_stats.st_mtime,
                                "duration": None,
                                "thumbnail_url": None
                            }
                            videos.append(video_info)
                            
                    except (HTTPException, OSError):
                        continue
                        
            except HTTPException:
                continue
        
        # Sort by creation time (newest first)
        videos.sort(key=lambda x: x["created_at"], reverse=True)
        
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        return []
    
    return videos

@router.get("/videos/{streamer_name}/{filename}")
async def stream_video(streamer_name: str, filename: str, request: Request):
    """Stream a video file with range request support - CodeQL-safe implementation"""
    try:
        recordings_dir = get_recordings_directory()
        if not recordings_dir:
            raise HTTPException(status_code=500, detail="Recordings directory not configured")
        
        # Enhanced input validation
        if not streamer_name or not filename:
            raise HTTPException(status_code=400, detail="Missing parameters")
        
        # URL decode the filename
        try:
            decoded_filename = urllib.parse.unquote(filename)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid filename encoding")
        
        # Validate character sets
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_name):
            raise HTTPException(status_code=400, detail="Invalid streamer name")
        
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', decoded_filename):
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Security check: verify it's a video file
        if not is_video_file(decoded_filename):
            raise HTTPException(status_code=400, detail="Not a video file")
        
        # Get file path safely (completely isolated from user input)
        try:
            file_path = safe_file_access(recordings_dir, streamer_name, decoded_filename)
        except HTTPException:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Verify file exists and is accessible
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get file info
        try:
            file_size = file_path.stat().st_size
        except OSError:
            raise HTTPException(status_code=500, detail="Error accessing file")
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "video/mp4"
          # Handle range requests
        range_header = request.headers.get('range')
        if range_header:
            # Parse range header
            try:
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if not range_match:
                    raise HTTPException(status_code=400, detail="Invalid range header")
                
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                
                if start >= file_size or end >= file_size or start > end:
                    raise HTTPException(status_code=416, detail="Range not satisfiable")
                
                chunk_size = end - start + 1
                
                def generate_chunk():
                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        remaining = chunk_size
                        while remaining > 0:
                            read_size = min(8192, remaining)
                            data = f.read(read_size)
                            if not data:
                                break
                            remaining -= len(data)
                            yield data
                
                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                    "Content-Type": mime_type
                }
                
                return StreamingResponse(
                    generate_chunk(),
                    status_code=206,
                    headers=headers
                )
            except Exception as e:
                logger.error(f"Range request processing failed: {e}")
                # Fall through to return full file
        
        # Return full file
        return FileResponse(
            file_path,
            media_type=mime_type,
            filename=decoded_filename
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {streamer_name}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=safe_error_message(e))

@router.get("/videos/{streamer_name}")
async def get_streamer_videos(streamer_name: str):
    """Get all videos for a specific streamer - CodeQL-safe implementation"""
    try:
        # Validate streamer name
        if not streamer_name or not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_name):
            raise HTTPException(status_code=400, detail="Invalid streamer name")
        
        recordings_dir = get_recordings_directory()
        if not recordings_dir:
            raise HTTPException(status_code=500, detail="Recordings directory not configured")
        
        # Get streamer directory safely
        try:
            streamer_path = safe_file_access(recordings_dir, streamer_name)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Streamer not found")
        
        if not streamer_path.exists() or not streamer_path.is_dir():
            raise HTTPException(status_code=404, detail="Streamer not found")
        
        videos = []
        
        # List files safely
        try:
            filenames = list_safe_directory(recordings_dir, streamer_name)
        except HTTPException:
            return videos
        
        for filename in filenames:
            if not is_video_file(filename):
                continue
            
            try:
                # Get file path safely
                file_path = safe_file_access(recordings_dir, streamer_name, filename)
                
                if file_path.is_file():
                    file_stats = file_path.stat()
                    video_info = {
                        "title": filename,
                        "streamer_name": streamer_name,
                        "file_path": str(file_path),
                        "file_size": file_stats.st_size,
                        "created_at": file_stats.st_mtime,
                        "duration": None,
                        "thumbnail_url": None
                    }
                    videos.append(video_info)
                    
            except (HTTPException, OSError):
                continue
        
        # Sort by creation time (newest first)
        videos.sort(key=lambda x: x["created_at"], reverse=True)
        
        return videos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting videos for streamer {streamer_name}: {e}")
        raise HTTPException(status_code=500, detail=safe_error_message(e))
