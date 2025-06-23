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
            streamer_path = os.path.join(recordings_dir, streamer_name)
            
            if not os.path.isdir(streamer_path):
                continue
                
            # Look for video files in streamer directory
            for filename in os.listdir(streamer_path):
                file_path = os.path.join(streamer_path, filename)
                
                # Check if it's a video file
                if is_video_file(filename) and os.path.isfile(file_path):
                    try:
                        file_stats = os.stat(file_path)
                        
                        video_info = {
                            "title": filename,
                            "streamer_name": streamer_name,
                            "file_path": file_path,
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
        # URL decode the filename
        decoded_filename = urllib.parse.unquote(filename)
        logger.info(f"Streaming video: {streamer_name}/{decoded_filename}")
        
        # Get recordings directory
        recordings_dir = get_recordings_directory()
        if not os.path.isabs(recordings_dir):
            recordings_dir = os.path.abspath(recordings_dir)
        
        # Construct file path
        file_path = os.path.join(recordings_dir, streamer_name, decoded_filename)
        
        # Security check - ensure path is within recordings directory
        if not os.path.abspath(file_path).startswith(os.path.abspath(recordings_dir)):
            logger.warning(f"Attempted path traversal: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Get file stats
        file_size = os.path.getsize(file_path)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
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
            
            # Create streaming response for range
            def generate_chunk():
                with open(file_path, "rb") as f:
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
            )
        else:
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
        raise HTTPException(status_code=500, detail=f"Error streaming video: {str(e)}")

@router.get("/videos/{streamer_name}")
async def get_streamer_videos(streamer_name: str):
    """Get all videos for a specific streamer"""
    try:
        videos = []
        recordings_dir = get_recordings_directory()
        if not os.path.isabs(recordings_dir):
            recordings_dir = os.path.abspath(recordings_dir)
            
        streamer_path = os.path.join(recordings_dir, streamer_name)
        
        if not os.path.exists(streamer_path):
            logger.warning(f"Streamer directory {streamer_path} does not exist")
            return videos
        
        for filename in os.listdir(streamer_path):
            file_path = os.path.join(streamer_path, filename)
            
            if is_video_file(filename) and os.path.isfile(file_path):
                try:
                    file_stats = os.stat(file_path)
                    
                    video_info = {
                        "title": filename,
                        "streamer_name": streamer_name,
                        "file_path": file_path,
                        "file_size": file_stats.st_size,
                        "created_at": file_stats.st_mtime,
                        "duration": None,
                        "thumbnail_url": None
                    }
                    
                    videos.append(video_info)
                    
                except Exception as e:
                    logger.error(f"Error processing video file {file_path}: {e}")
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
