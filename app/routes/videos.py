from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
import os
import urllib.parse
from typing import List, Optional
import logging
from pathlib import Path
import mimetypes
import re
from datetime import datetime
from secrets import token_urlsafe
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.models import RecordingSettings, Stream, Streamer, Recording, StreamMetadata
from app.utils.security_enhanced import safe_file_access, safe_error_message, list_safe_directory
from app.utils.streamer_cache import get_valid_streamers
from app.utils.token_store import store_share_token, validate_share_token, cleanup_expired_tokens
from app.services.core.auth_service import AuthService

logger = logging.getLogger("streamvault")

# Constants for share tokens and chapters
TOKEN_EXPIRATION_HOURS = 24  # Share token expiration time
TOKEN_EXPIRATION_SECONDS = TOKEN_EXPIRATION_HOURS * 60 * 60  # Convert to seconds
CHAPTER_INTERVAL_SECONDS = 600  # 10 minutes in seconds
MAX_CHAPTERS = 20  # Maximum number of chapters to prevent too many for very long streams

def parse_vtt_chapters(vtt_content: str) -> list:
    """Parse WebVTT chapter format - improved version matching working streamers implementation"""
    chapters = []
    
    # Split into cues by looking for timestamp lines
    lines = vtt_content.split('\n')
    current_chapter = None
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and WebVTT header
        if not line or line == 'WEBVTT':
            continue
        
        # Look for timestamp lines (format: 00:00:00.000 --> 00:00:00.000)
        timestamp_match = re.match(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})', line)
        if timestamp_match:
            if current_chapter:
                chapters.append(current_chapter)
            
            start_time = timestamp_match.group(1)
            
            # Convert timestamp to seconds for consistency
            time_parts = start_time.split(':')
            if len(time_parts) == 3:
                hours, minutes, seconds = time_parts
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            else:
                logger.warning(f"Invalid timestamp format encountered: {start_time}")
                continue
            
            current_chapter = {
                "id": len(chapters) + 1,
                "start": total_seconds,
                "start_time": start_time,
                "title": "",
                "type": "chapter"
            }
        # Skip lines that are not relevant to chapter titles (e.g., WebVTT metadata or cue types)
        elif current_chapter and line and not any(line.startswith(prefix) for prefix in ['NOTE', 'STYLE', 'REGION', 'COMMENT']):
            # This is the chapter title
            if not current_chapter["title"]:
                current_chapter["title"] = line
            else:
                # Multi-line title
                current_chapter["title"] += " " + line
    
    # Add the last chapter
    if current_chapter:
        chapters.append(current_chapter)
    
    return chapters

def parse_ffmpeg_chapters(ffmpeg_content: str) -> list:
    """Parse FFmpeg chapter format"""
    chapters = []
    chapter_blocks = re.split(r'\[CHAPTER\]', ffmpeg_content)
    
    for block in chapter_blocks:
        if not block.strip():
            continue
            
        lines = block.strip().split('\n')
        start_time = None
        title = None
        
        for line in lines:
            if line.startswith('TIMEBASE='):
                continue
            elif line.startswith('START='):
                # Extract start time in timebase units
                start_value = line.split('=')[1]
                try:
                    start_time = float(start_value)
                except (ValueError, IndexError):
                    continue
            elif line.startswith('title='):
                title = line.split('=', 1)[1] if '=' in line else None
        
        if start_time is not None:
            chapters.append({
                'id': len(chapters) + 1,
                'start': start_time,
                'title': title or f"Chapter {len(chapters) + 1}"
            })
    
    return chapters

def get_video_thumbnail_url(stream_id: int, recording_path: str) -> Optional[str]:
    """Get the correct thumbnail URL for a video"""
    try:
        recording_path_obj = Path(recording_path)
        base_filename = recording_path_obj.stem
        video_dir = recording_path_obj.parent
        
        # Priority order for thumbnail files:
        # 1. {base_filename}-thumb.jpg (Plex format, usually correct)
        # 2. {base_filename}_thumbnail.jpg (fallback)
        
        thumbnail_candidates = [
            video_dir / f"{base_filename}-thumb.jpg",
            video_dir / f"{base_filename}_thumbnail.jpg",
        ]
        
        for thumbnail_path in thumbnail_candidates:
            if thumbnail_path.exists() and thumbnail_path.is_file():
                # Return relative URL for API access
                return f"/api/videos/{stream_id}/thumbnail"
        
        return None
    except Exception as e:
        logger.error(f"Error getting thumbnail for stream {stream_id}: {e}")
        return None

router = APIRouter(
    prefix="/api",
    tags=["videos"]
)

def secure_filename(filename):
    """Secure a filename by removing or replacing dangerous characters"""
    if not filename:
        return ""
    
    # Remove path separators and other dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\.\.+', '.', filename)  # Remove multiple dots
    filename = filename.strip('. ')  # Remove leading/trailing dots and spaces
    
    # Ensure filename is not empty after sanitization
    if not filename:
        return "file"
    
    return filename

def get_recordings_directory():
    """Get the recordings directory - hardcoded for Docker consistency"""
    return "/recordings"

def is_video_file(filename: str) -> bool:
    """Check if a file is a video file based on its extension"""
    video_extensions = {'.mp4', '.avi', '.mkv', '.flv', '.ts', '.m4v', '.webm', '.mov'}
    return Path(filename).suffix.lower() in video_extensions

@router.get("/videos")
async def get_videos(request: Request, db: Session = Depends(get_db)):
    """Get all videos from database with file verification"""
    # Check authentication via session cookie
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate session
    auth_service = AuthService(db)
    if not await auth_service.validate_session(session_token):
        raise HTTPException(status_code=401, detail="Invalid session")
    
    videos = []
    
    try:
        # Strategy 1: Get videos from streams that have recording_path set
        streams_with_paths = db.query(Stream, Streamer).join(
            Streamer, Stream.streamer_id == Streamer.id
        ).filter(
            Stream.recording_path.isnot(None),
            Stream.recording_path != ""
        ).order_by(Stream.started_at.desc()).all()
        
        logger.debug(f"Found {len(streams_with_paths)} streams with recording paths")
        
        for stream, streamer in streams_with_paths:
            try:
                recording_path = Path(stream.recording_path)
                
                if recording_path.exists() and recording_path.is_file():
                    file_stats = recording_path.stat()
                    
                    duration = None
                    if stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()
                    
                    video_info = {
                        "id": stream.id,
                        "title": stream.title or f"Stream {stream.id}",
                        "streamer_name": streamer.username,
                        "streamer_id": streamer.id,
                        "file_path": str(recording_path),
                        "file_size": file_stats.st_size,
                        "created_at": stream.started_at.isoformat() if stream.started_at else None,
                        "started_at": stream.started_at.isoformat() if stream.started_at else None,
                        "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                        "duration": duration,
                        "category_name": stream.category_name,
                        "language": stream.language,
                        "thumbnail_url": get_video_thumbnail_url(stream.id, str(recording_path))
                    }
                    videos.append(video_info)
                    logger.debug(f"Added video from stream: {stream.title} by {streamer.username}")
                    
            except Exception as e:
                logger.error(f"Error processing stream {stream.id}: {e}")
                continue
        
        # Strategy 2: Get videos from recordings that have valid files but no recording_path in stream
        recordings_with_files = db.query(Recording, Stream, Streamer).join(
            Stream, Recording.stream_id == Stream.id
        ).join(
            Streamer, Stream.streamer_id == Streamer.id
        ).filter(
            Recording.path.isnot(None),
            Recording.path != "",
            Recording.status.in_(['completed', 'post_processing'])
        ).order_by(Recording.start_time.desc()).all()
        
        logger.debug(f"Found {len(recordings_with_files)} recordings with file paths")
        
        # Keep track of streams we've already added to avoid duplicates
        added_stream_ids = {video["id"] for video in videos}
        
        for recording, stream, streamer in recordings_with_files:
            # Skip if we already added this stream
            if stream.id in added_stream_ids:
                continue
                
            try:
                # Try both .ts and .mp4 files
                recording_path = Path(recording.path)
                mp4_path = recording_path.with_suffix('.mp4')
                
                final_path = None
                file_stats = None
                
                # Prefer .mp4 if it exists
                if mp4_path.exists():
                    final_path = mp4_path
                    file_stats = mp4_path.stat()
                elif recording_path.exists():
                    final_path = recording_path
                    file_stats = recording_path.stat()
                
                if final_path and file_stats:
                    # Update the stream's recording_path for future use (self-healing)
                    if not stream.recording_path:
                        stream.recording_path = str(final_path)
                        logger.debug(f"Auto-updated recording_path for stream {stream.id}: {final_path}")
                    
                    duration = None
                    if recording.start_time and recording.end_time:
                        duration = (recording.end_time - recording.start_time).total_seconds()
                    elif stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()
                    
                    video_info = {
                        "id": stream.id,
                        "title": stream.title or f"Stream {stream.id}",
                        "streamer_name": streamer.username,
                        "streamer_id": streamer.id,
                        "file_path": str(final_path),
                        "file_size": file_stats.st_size,
                        "created_at": (recording.start_time or stream.started_at).isoformat() if (recording.start_time or stream.started_at) else None,
                        "started_at": (recording.start_time or stream.started_at).isoformat() if (recording.start_time or stream.started_at) else None,
                        "ended_at": (recording.end_time or stream.ended_at).isoformat() if (recording.end_time or stream.ended_at) else None,
                        "duration": duration,
                        "category_name": stream.category_name,
                        "language": stream.language,
                        "thumbnail_url": get_video_thumbnail_url(stream.id, str(final_path))
                    }
                    videos.append(video_info)
                    added_stream_ids.add(stream.id)
                    logger.debug(f"Added video from recording: {stream.title} by {streamer.username}")
                    
            except Exception as e:
                logger.error(f"Error processing recording {recording.id}: {e}")
                continue
        
        # Commit any auto-updates to recording_path
        if len(videos) > len(streams_with_paths):
            db.commit()
            logger.debug(f"Auto-updated {len(videos) - len(streams_with_paths)} recording paths")
        
        logger.info(f"Returning {len(videos)} videos")
        
    except Exception as e:
        logger.error(f"Error getting videos from database: {e}")
        return []
    
    return videos

@router.get("/videos/debug/{stream_id}")
async def debug_video_access(stream_id: int, request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to test video access without streaming"""
    try:
        logger.info(f"DEBUG VIDEO ACCESS: stream_id={stream_id}")
        logger.info(f"DEBUG: Request headers: {dict(request.headers)}")
        logger.info(f"DEBUG: Request cookies: {dict(request.cookies)}")
        
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            logger.error("DEBUG: No session token found")
            return {"error": "No session token", "headers": dict(request.headers)}
        
        logger.info(f"DEBUG: Session token found: {session_token[:20]}...")
        
        # Validate session
        auth_service = AuthService(db)
        session_valid = await auth_service.validate_session(session_token)
        logger.info(f"DEBUG: Session validation result: {session_valid}")
        
        if not session_valid:
            logger.error("DEBUG: Session validation failed")
            return {"error": "Session validation failed", "token": session_token[:20]}
        
        # Get stream from database
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            logger.error(f"DEBUG: Stream not found: stream_id={stream_id}")
            return {"error": "Stream not found", "stream_id": stream_id}
        
        logger.info(f"DEBUG: Found stream: {stream.title}, recording_path: {stream.recording_path}")
        
        if not stream.recording_path:
            return {"error": "No recording path", "stream": {"id": stream.id, "title": stream.title}}
        
        file_path = Path(stream.recording_path)
        file_exists = file_path.exists()
        
        logger.info(f"DEBUG: File path: {file_path}, exists: {file_exists}")
        
        result = {
            "success": True,
            "stream_id": stream_id,
            "stream": {
                "id": stream.id,
                "title": stream.title,
                "recording_path": stream.recording_path,
            },
            "file": {
                "path": str(file_path),
                "exists": file_exists,
                "size": file_path.stat().st_size if file_exists else 0,
            },
            "session": {
                "token": session_token[:20] + "...",
                "valid": session_valid,
            }
        }
        
        logger.info(f"DEBUG: Result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"DEBUG: Exception: {e}")
        # Don't expose internal error details to users
        return {"error": "Internal error occurred", "success": False}

@router.post("/videos/{stream_id}/share-token")
async def generate_share_token(stream_id: int, request: Request, db: Session = Depends(get_db)):
    """Generate a secure temporary share token for external video access (VLC, etc.)"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        auth_service = AuthService(db)
        if not await auth_service.validate_session(session_token):
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Check if stream exists
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream or not stream.recording_path:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Generate a secure temporary share token
        share_token = token_urlsafe(32)  # Generate a secure random token
        
        # Store the share token with expiration
        store_share_token(share_token, stream_id, TOKEN_EXPIRATION_SECONDS)
        
        # Clean up any expired tokens while we're here
        cleanup_expired_tokens()
        
        # Create the share URL using BASE_URL from settings (ensures correct HTTPS URL)
        from app.config.settings import get_settings
        settings = get_settings()
        base_url = settings.BASE_URL.rstrip('/')
        share_url = f"{base_url}/api/videos/public/{stream_id}?token={share_token}"
        
        return JSONResponse(content={
            "success": True,
            "share_url": share_url,
            "expires_in": f"{TOKEN_EXPIRATION_HOURS} hours"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating share token: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate share token")

@router.get("/videos/{stream_id}/thumbnail")
async def get_video_thumbnail(stream_id: int, request: Request, db: Session = Depends(get_db)):
    """Serve video thumbnail image"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        auth_service = AuthService(db)
        if not await auth_service.validate_session(session_token):
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Get stream from database
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream or not stream.recording_path:
            raise HTTPException(status_code=404, detail="Stream or recording not found")
        
        recording_path = Path(stream.recording_path)
        base_filename = recording_path.stem
        video_dir = recording_path.parent
        
        # Priority order for thumbnail files (use the correct one, not the black one)
        thumbnail_candidates = [
            video_dir / f"{base_filename}-thumb.jpg",        # Plex format (usually correct)
            video_dir / f"{base_filename}_thumbnail.jpg",    # Fallback format
        ]
        
        thumbnail_path = None
        for candidate in thumbnail_candidates:
            if candidate.exists() and candidate.is_file():
                thumbnail_path = candidate
                break
        
        if not thumbnail_path:
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        # Return the thumbnail file
        return FileResponse(
            str(thumbnail_path),
            media_type="image/jpeg",
            filename=f"thumbnail_{stream_id}.jpg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail for stream {stream_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/public/{stream_id}")
async def stream_video_public(stream_id: int, token: str = Query(...), request: Request = None, db: Session = Depends(get_db)):
    """Stream video with token-based authentication for external players like VLC"""
    try:
        logger.info(f"Public video stream request for stream_id: {stream_id} with token: {token[:20]}...")
        
        # Validate the share token
        token_stream_id = validate_share_token(token)
        if not token_stream_id or token_stream_id != stream_id:
            # Also try validating as a session token for backward compatibility
            auth_service = AuthService(db)
            if not await auth_service.validate_session(token):
                raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Get stream from database
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream or not stream.recording_path:
            logger.error(f"Stream not found or no recording path: stream_id={stream_id}")
            raise HTTPException(status_code=404, detail="Video not found")
        
        file_path = Path(stream.recording_path)
        
        # Verify file exists
        if not file_path.exists() or not file_path.is_file():
            logger.error(f"Video file not found: {stream.recording_path}")
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Get file info
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            logger.error(f"Error accessing file: {e}")
            raise HTTPException(status_code=500, detail="Error accessing file")
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "video/mp4"
            
        # Handle range requests (important for seeking in VLC)
        range_header = request.headers.get('range') if request else None
        if range_header:
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
                    with open(str(file_path), 'rb') as f:
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
                    "Content-Type": mime_type,
                    "Cache-Control": "no-cache"
                }
                
                return StreamingResponse(
                    generate_chunk(),
                    status_code=206,
                    headers=headers
                )
            except ValueError:
                # Invalid range header, serve full file
                pass
        
        # No range request, stream entire file
        def generate_file():
            with open(str(file_path), 'rb') as f:
                while True:
                    data = f.read(8192)
                    if not data:
                        break
                    yield data
        
        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Type": mime_type,
            "Cache-Control": "no-cache"
        }
        
        return StreamingResponse(
            generate_file(),
            headers=headers
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming public video {stream_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/{stream_id}/stream")
async def stream_video_by_id(stream_id: int, request: Request, db: Session = Depends(get_db)):
    """Stream a video file by stream ID with range request support"""
    try:
        logger.info(f"Video stream request for stream_id: {stream_id}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Cookies: {request.cookies}")
        
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            logger.error("No session token found in cookies")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        logger.info(f"Session token found: {session_token[:10]}...")
        
        # Validate session
        try:
            auth_service = AuthService(db)
            session_valid = await auth_service.validate_session(session_token)
            logger.info(f"Session validation result: {session_valid}")
            
            if not session_valid:
                logger.error("Session validation failed")
                raise HTTPException(status_code=401, detail="Invalid session")
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            raise HTTPException(status_code=401, detail="Session validation error")
        
        # Get stream from database
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream or not stream.recording_path:
            logger.error(f"Stream not found or no recording path: stream_id={stream_id}")
            raise HTTPException(status_code=404, detail="Video not found")
        
        logger.info(f"Found stream: {stream.title}, recording_path: {stream.recording_path}")
        
        file_path = Path(stream.recording_path)
        
        # Verify file exists
        if not file_path.exists() or not file_path.is_file():
            logger.error(f"Video file not found: {stream.recording_path}")
            raise HTTPException(status_code=404, detail="Video file not found")
        
        logger.info(f"Video file exists: {file_path}")
        
        # Get file info
        try:
            file_size = file_path.stat().st_size
            logger.info(f"File size: {file_size} bytes")
        except OSError as e:
            logger.error(f"Error accessing file: {e}")
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
                    with open(str(file_path), 'rb') as f:
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
                    "Content-Type": mime_type,
                    "Cache-Control": "no-cache"
                }
                
                return StreamingResponse(
                    generate_chunk(),
                    status_code=206,
                    headers=headers
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid range header")
        else:
            # No range request, stream entire file
            def generate_file():
                with open(str(file_path), 'rb') as f:
                    while True:
                        data = f.read(8192)
                        if not data:
                            break
                        yield data
            
            headers = {
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Type": mime_type,
                "Cache-Control": "no-cache"
            }
            
            return StreamingResponse(
                generate_file(),
                headers=headers
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {stream_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/{stream_id}/chapters")
async def get_video_chapters(stream_id: int, request: Request, db: Session = Depends(get_db)):
    """Get chapters for a video from metadata files"""
    try:
        logger.info(f"🎬 CHAPTER_REQUEST: Getting chapters for stream {stream_id}")
        
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            logger.warning(f"🎬 CHAPTER_AUTH_FAIL: No session token for stream {stream_id}")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        auth_service = AuthService(db)
        if not await auth_service.validate_session(session_token):
            logger.warning(f"🎬 CHAPTER_SESSION_INVALID: Invalid session for stream {stream_id}")
            raise HTTPException(status_code=401, detail="Invalid session")
        
        logger.info(f"🎬 CHAPTER_AUTH_OK: Authentication successful for stream {stream_id}")
        
        # Get stream from database
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            logger.warning(f"🎬 CHAPTER_STREAM_NOT_FOUND: Stream {stream_id} not found")
            raise HTTPException(status_code=404, detail="Stream not found")
        
        logger.info(f"🎬 CHAPTER_STREAM_FOUND: Stream {stream_id} - {stream.title}")
        
        # Get metadata for this stream
        from app.models import StreamMetadata
        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
        
        chapters = []
        
        # Try to load chapters from VTT file first (best for web)
        if metadata and metadata.chapters_vtt_path and Path(metadata.chapters_vtt_path).exists():
            try:
                with open(metadata.chapters_vtt_path, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()
                    chapters = parse_vtt_chapters(vtt_content)
                    logger.info(f"🎬 CHAPTER_VTT_LOADED: Loaded {len(chapters)} chapters from VTT file")
            except Exception as e:
                logger.warning(f"🎬 CHAPTER_VTT_FAIL: Failed to load VTT chapters: {e}")
        
        # Fallback to FFmpeg chapters format if VTT not available
        if not chapters and metadata and metadata.chapters_ffmpeg_path and Path(metadata.chapters_ffmpeg_path).exists():
            try:
                with open(metadata.chapters_ffmpeg_path, 'r', encoding='utf-8') as f:
                    ffmpeg_content = f.read()
                    chapters = parse_ffmpeg_chapters(ffmpeg_content)
                    logger.info(f"🎬 CHAPTER_FFMPEG_LOADED: Loaded {len(chapters)} chapters from FFmpeg file")
            except Exception as e:
                logger.warning(f"🎬 CHAPTER_FFMPEG_FAIL: Failed to load FFmpeg chapters: {e}")
        
        # If no chapters found, create some sample ones for testing if duration exists
        if not chapters and stream.started_at and stream.ended_at:
            duration = (stream.ended_at - stream.started_at).total_seconds()
            if duration > 60:  # Only create chapters for streams longer than 1 minute
                # Create chapters every 10 minutes
                chapter_interval = CHAPTER_INTERVAL_SECONDS  # Fixed 10-minute intervals
                current_time = 0
                chapter_num = 1
                
                while current_time < duration and chapter_num <= MAX_CHAPTERS:
                    chapters.append({
                        "id": chapter_num,
                        "title": f"Chapter {chapter_num}",
                        "start": current_time,
                        "end": min(current_time + chapter_interval, duration)
                    })
                    current_time += chapter_interval
                    chapter_num += 1
                logger.info(f"🎬 CHAPTER_GENERATED: Generated {len(chapters)} sample chapters")
        
        # If still no chapters, create a single default chapter
        if not chapters:
            chapters = [{
                "id": 1,
                "title": stream.title or f"Stream {stream_id}",
                "start": 0,
                "end": 0
            }]
            logger.info(f"🎬 CHAPTER_DEFAULT: Created default chapter")
        
        logger.info(f"🎬 CHAPTER_SUCCESS: Returning {len(chapters)} chapters for stream {stream_id}")
        return chapters
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🎬 CHAPTER_ERROR: Error getting chapters for stream {stream_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/{streamer_name}/{filename}")
async def stream_video(streamer_name: str, filename: str, request: Request, db: Session = Depends(get_db)):
    """Stream a video file with range request support - CodeQL-safe implementation"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        auth_service = AuthService(db)
        if not await auth_service.validate_session(session_token):
            raise HTTPException(status_code=401, detail="Invalid session")
        
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
                    with open(str(file_path), 'rb') as f:
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
            str(file_path),
            media_type=mime_type,
            filename=decoded_filename
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {streamer_name}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=safe_error_message(e))

@router.get("/videos/{streamer_name}")
async def get_streamer_videos(streamer_name: str, request: Request, db: Session = Depends(get_db)):
    """Get all videos for a specific streamer - CodeQL-safe implementation"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        auth_service = AuthService(db)
        if not await auth_service.validate_session(session_token):
            raise HTTPException(status_code=401, detail="Invalid session")
        
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

@router.get("/videos/streamer/{streamer_id}")
async def get_videos_by_streamer(streamer_id: int, request: Request, db: Session = Depends(get_db)):
    """Get all videos for a specific streamer"""
    # Check authentication via session cookie
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate session
    auth_service = AuthService(db)
    if not await auth_service.validate_session(session_token):
        raise HTTPException(status_code=401, detail="Invalid session")
    
    videos = []
    
    try:
        # Query streams for specific streamer
        streams = db.query(Stream, Streamer).join(
            Streamer, Stream.streamer_id == Streamer.id
        ).filter(
            Stream.streamer_id == streamer_id,
            Stream.recording_path.isnot(None),
            Stream.recording_path != ""
        ).order_by(Stream.started_at.desc()).all()
        
        logger.debug(f"Found {len(streams)} videos for streamer {streamer_id}")
        
        for stream, streamer in streams:
            try:
                # Verify the file exists
                recording_path = Path(stream.recording_path)
                
                if recording_path.exists() and recording_path.is_file():
                    file_stats = recording_path.stat()
                    
                    # Calculate duration if available
                    duration = None
                    if stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()
                    
                    video_info = {
                        "id": stream.id,
                        "title": stream.title or f"Stream {stream.id}",
                        "streamer_name": streamer.username,
                        "streamer_id": streamer.id,
                        "file_path": str(recording_path),
                        "file_size": file_stats.st_size,
                        "created_at": stream.started_at.isoformat() if stream.started_at else None,
                        "started_at": stream.started_at.isoformat() if stream.started_at else None,
                        "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                        "duration": duration,
                        "category_name": stream.category_name,
                        "language": stream.language,
                        "thumbnail_url": get_video_thumbnail_url(stream.id, str(recording_path))
                    }
                    videos.append(video_info)
                else:
                    logger.warning(f"Recording file not found: {stream.recording_path}")
                    
            except Exception as e:
                logger.error(f"Error processing stream {stream.id}: {e}")
                continue
        
        logger.info(f"Returning {len(videos)} videos for streamer {streamer_id}")
        
    except Exception as e:
        logger.error(f"Error getting videos for streamer {streamer_id}: {e}")
        return []
    
    return videos

@router.get("/videos/stream_by_filename/{filename}")
async def stream_video_by_filename(filename: str, request: Request, db: Session = Depends(get_db)):
    """Stream video by filename for direct access"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        auth_service = AuthService(db)
        if not await auth_service.validate_session(session_token):
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # URL decode the filename
        try:
            decoded_filename = urllib.parse.unquote(filename)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid filename encoding")
        
        # Security: Sanitize filename
        sanitized_filename = secure_filename(decoded_filename)
        if not sanitized_filename or sanitized_filename != decoded_filename:
            raise HTTPException(status_code=400, detail="Invalid or unsafe filename")
        
        recordings_dir = get_recordings_directory()
        if not recordings_dir:
            raise HTTPException(status_code=500, detail="Recordings directory not configured")
        
        # Security: Only allow video files and use safe file access
        if not is_video_file(sanitized_filename):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Use safe file access to prevent path injection
        try:
            # Create a safe path that isolates user input from path operations
            safe_path = safe_file_access(recordings_dir, "", sanitized_filename)
            if not safe_path.exists() or not safe_path.is_file():
                raise HTTPException(status_code=404, detail="Video file not found")
            
            # Use the safe path for all subsequent operations
            file_path = safe_path
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error accessing file {sanitized_filename}: {e}")
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Get file info using safe path
        try:
            file_size = file_path.stat().st_size
        except OSError:
            raise HTTPException(status_code=500, detail="Error accessing file")
        
        # Get MIME type using safe path
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "video/mp4"
        
        # Handle range requests for video streaming
        range_header = request.headers.get('range')
        if range_header:
            # Parse range header
            try:
                ranges = range_header.replace('bytes=', '').split('-')
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if ranges[1] else file_size - 1
                
                # Validate range
                if start >= file_size or end >= file_size or start > end:
                    raise HTTPException(status_code=416, detail="Range not satisfiable")
                
                chunk_size = end - start + 1
                
                def generate_chunk():
                    # Use safe path for file operations
                    with open(str(file_path), 'rb') as f:
                        f.seek(start)
                        remaining = chunk_size
                        while remaining > 0:
                            chunk = f.read(min(8192, remaining))
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk
                
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
                
            except ValueError:
                # Invalid range header, serve full file
                pass
        
        # Return full file using safe path
        return FileResponse(
            str(file_path),
            media_type=mime_type,
            filename=decoded_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in stream_video_by_filename: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/test/{stream_id}")
async def test_video_access(stream_id: int, request: Request, db: Session = Depends(get_db)):
    """Test endpoint to debug video access issues"""
    try:
        logger.info(f"Test video access for stream_id: {stream_id}")
        
        # Check cookies
        session_token = request.cookies.get("session")
        logger.info(f"Session token: {'Found' if session_token else 'Not found'}")
        
        if session_token:
            # Test session validation
            auth_service = AuthService(db)
            session_valid = await auth_service.validate_session(session_token)
            logger.info(f"Session valid: {session_valid}")
        
        # Check if stream exists
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            return {"error": "Stream not found", "stream_id": stream_id}
        
        # Check if file exists
        if not stream.recording_path:
            return {"error": "No recording path", "stream": {"id": stream.id, "title": stream.title}}
        
        file_path = Path(stream.recording_path)
        file_exists = file_path.exists()
        file_size = file_path.stat().st_size if file_exists else 0
        
        return {
            "stream_id": stream_id,
            "stream_title": stream.title,
            "recording_path": stream.recording_path,
            "file_exists": file_exists,
            "file_size": file_size,
            "session_token_present": bool(session_token),
            "session_valid": session_valid if session_token else False,
            "headers": dict(request.headers),
            "cookies": dict(request.cookies)
        }
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}", exc_info=True)
        return {"error": "An internal error has occurred"}


@router.get("/stream/{stream_id}/has-recording")
async def check_stream_has_recording(stream_id: int, db: Session = Depends(get_db)):
    """Check if a specific stream has a recording available - simplified version"""
    
    try:
        # Get the stream
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Method 1: Check stream.recording_path (legacy system)
        if stream.recording_path and stream.recording_path.strip():
            recording_path = Path(stream.recording_path)
            if recording_path.exists() and recording_path.is_file():
                return {
                    "has_recording": True,
                    "file_path": str(recording_path),
                    "file_size": recording_path.stat().st_size,
                    "method": "stream_recording_path"
                }
        
        # Method 2: Check Recording model (new system)
        recording = db.query(Recording).filter(
            Recording.stream_id == stream_id,
            Recording.status == "completed"
        ).first()
        
        if recording and recording.path and recording.path.strip():
            recording_path = Path(recording.path)
            if recording_path.exists() and recording_path.is_file():
                return {
                    "has_recording": True,
                    "file_path": str(recording_path),
                    "file_size": recording_path.stat().st_size,
                    "method": "recording_model"
                }
        
        # No recording found
        return {
            "has_recording": False,
            "method": "none"
        }
        
    except Exception as e:
        logger.error(f"Error checking recording for stream {stream_id}: {e}")
        return {
            "has_recording": False,
            "error": "An internal error occurred while checking the recording.",
            "method": "error"
        }


@router.post("/streams/check-recordings")
async def check_multiple_streams_recordings(stream_ids: List[int], db: Session = Depends(get_db)):
    """Check recording availability for multiple streams at once - simplified version"""
    
    results = {}
    
    try:
        # Get all streams at once
        streams = db.query(Stream).filter(Stream.id.in_(stream_ids)).all()
        
        # Get all recordings for these streams at once
        recordings = db.query(Recording).filter(
            Recording.stream_id.in_(stream_ids),
            Recording.status == "completed"
        ).all()
        
        # Create recording lookup by stream_id
        # Note: If multiple completed recordings exist for the same stream, 
        # this intentionally keeps only the most recent one (last in query result)
        recordings_by_stream = {rec.stream_id: rec for rec in recordings}
        
        for stream in streams:
            # Method 1: Check stream.recording_path (legacy system)
            if stream.recording_path and stream.recording_path.strip():
                try:
                    recording_path = Path(stream.recording_path)
                    if recording_path.exists() and recording_path.is_file():
                        results[stream.id] = {
                            "has_recording": True,
                            "file_path": str(recording_path),
                            "file_size": recording_path.stat().st_size,
                            "method": "stream_recording_path"
                        }
                        continue
                except Exception:
                    pass
            
            # Method 2: Check Recording model (new system)
            recording = recordings_by_stream.get(stream.id)
            if recording and recording.path and recording.path.strip():
                try:
                    recording_path = Path(recording.path)
                    if recording_path.exists() and recording_path.is_file():
                        results[stream.id] = {
                            "has_recording": True,
                            "file_path": str(recording_path),
                            "file_size": recording_path.stat().st_size,
                            "method": "recording_model"
                        }
                        continue
                except Exception:
                    pass
            
            # No recording found for this stream
            results[stream.id] = {"has_recording": False, "method": "none"}
        
        # Add results for any stream IDs that weren't found in database
        for stream_id in stream_ids:
            if stream_id not in results:
                results[stream_id] = {"has_recording": False, "method": "stream_not_found"}
        
        return {
            "success": True,
            "data": results
        }
        
    except Exception as e:
        logger.error(f"Error checking stream recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Stream recording check failed due to an internal error.")


@router.get("/debug/videos-database")
async def debug_videos_database(
    db: Session = Depends(get_db),
    streamer_username: str = Query(None, description="Filter by specific streamer username")
):
    """Debug endpoint to see what's in the database vs filesystem"""
    
    result = {
        "streams": [],
        "recordings": [],
        "filesystem_check": {},
        "summary": {},
        "filter": {
            "streamer_username": streamer_username,
            "available_streamers": []
        }
    }
    
    # Get available streamers for reference
    available_streamers = db.query(Streamer.username).distinct().all()
    result["filter"]["available_streamers"] = [s.username for s in available_streamers]
    
    # Build query for streams
    streams_query = db.query(Stream, Streamer).join(
        Streamer, Stream.streamer_id == Streamer.id
    )
    
    # Apply filter if streamer_username is provided
    if streamer_username:
        streams_query = streams_query.filter(Streamer.username == streamer_username)
    
    streams = streams_query.order_by(Stream.started_at.desc()).limit(50).all()  # Limit for performance
    
    for stream, streamer in streams:
        stream_info = {
            "id": stream.id,
            "title": stream.title,
            "streamer_name": streamer.username,
            "started_at": stream.started_at.isoformat() if stream.started_at else None,
            "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
            "recording_path": stream.recording_path,
            "category_name": stream.category_name,
            "is_live": stream.is_live
        }
        
        # Check if recording_path file exists
        if stream.recording_path:
            try:
                path = Path(stream.recording_path)
                stream_info["recording_path_exists"] = path.exists()
                if path.exists():
                    stream_info["recording_path_size"] = path.stat().st_size
            except Exception as e:
                stream_info["recording_path_error"] = str(e)
        
        result["streams"].append(stream_info)
    
    # Build query for recordings
    recordings_query = db.query(Recording, Stream, Streamer).join(
        Stream, Recording.stream_id == Stream.id
    ).join(
        Streamer, Stream.streamer_id == Streamer.id
    )
    
    # Apply filter if streamer_username is provided
    if streamer_username:
        recordings_query = recordings_query.filter(Streamer.username == streamer_username)
    
    recordings = recordings_query.order_by(Recording.start_time.desc()).limit(50).all()  # Limit for performance
    
    for recording, stream, streamer in recordings:
        recording_info = {
            "id": recording.id,
            "stream_id": recording.stream_id,
            "status": recording.status,
            "path": recording.path,
            "start_time": recording.start_time.isoformat() if recording.start_time else None,
            "end_time": recording.end_time.isoformat() if recording.end_time else None,
            "stream_title": stream.title,
            "streamer_name": streamer.username
        }
        
        # Check if recording path file exists
        if recording.path:
            try:
                ts_path = Path(recording.path)
                mp4_path = ts_path.with_suffix('.mp4')
                
                recording_info["ts_path_exists"] = ts_path.exists()
                recording_info["mp4_path_exists"] = mp4_path.exists()
                
                if ts_path.exists():
                    recording_info["ts_path_size"] = ts_path.stat().st_size
                if mp4_path.exists():
                    recording_info["mp4_path_size"] = mp4_path.stat().st_size
                    recording_info["mp4_path"] = str(mp4_path)
                    
            except Exception as e:
                recording_info["path_check_error"] = str(e)
        
        result["recordings"].append(recording_info)
    
    # Check filesystem directly - build path based on streamer filter or scan all
    base_recordings_dir = Path("/recordings")
    if streamer_username and base_recordings_dir.exists():
        # Validate streamer_username using strict whitelist approach
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_username):
            result["filesystem_check"]["error"] = "Invalid streamer username format"
        else:
            # Get list of valid streamer directories from filesystem (cached whitelist approach)
            valid_streamers = get_valid_streamers(base_recordings_dir)
            
            # Check if requested streamer exists in whitelist
            if streamer_username not in valid_streamers:
                result["filesystem_check"]["error"] = f"Streamer directory not found: {streamer_username}"
                result["filesystem_check"]["available_streamers"] = valid_streamers
            else:
                # Safe path construction using validated name from filesystem
                streamer_recordings_dir = base_recordings_dir / streamer_username
                result["filesystem_check"]["recordings_dir_exists"] = True
                result["filesystem_check"]["streamer_dir"] = str(streamer_recordings_dir)
                
                # List subdirectories for the specific streamer
                subdirs = []
                for item in streamer_recordings_dir.iterdir():
                    if item.is_dir():
                        subdirs.append({
                            "name": item.name,
                            "files": []
                        })
                        # List files in subdirectory
                        for file in item.iterdir():
                            if file.suffix in ['.mp4', '.ts']:
                                subdirs[-1]["files"].append({
                                    "name": file.name,
                                    "size": file.stat().st_size,
                                    "path": str(file)
                                })
                
                result["filesystem_check"]["subdirectories"] = subdirs
    
    elif base_recordings_dir.exists():
        # Scan all streamer directories if no specific filter
        result["filesystem_check"]["recordings_dir_exists"] = True
        result["filesystem_check"]["all_streamers"] = []
        
        for streamer_dir in base_recordings_dir.iterdir():
            if streamer_dir.is_dir():
                result["filesystem_check"]["all_streamers"].append({
                    "name": streamer_dir.name,
                    "path": str(streamer_dir),
                    "file_count": len([f for f in streamer_dir.rglob("*") if f.is_file() and f.suffix in ['.mp4', '.ts']])
                })
    else:
        result["filesystem_check"]["recordings_dir_exists"] = False
    
    # Summary
    result["summary"] = {
        "total_streams": len(result["streams"]),
        "total_recordings": len(result["recordings"]),
        "streams_with_recording_path": len([s for s in result["streams"] if s.get("recording_path")]),
        "recordings_with_path": len([r for r in result["recordings"] if r.get("path")]),
        "mp4_files_found": len([r for r in result["recordings"] if r.get("mp4_path_exists")])
    }
    
    return result


@router.get("/debug/recordings-directory")
async def debug_recordings_directory(
    streamer_username: str = Query(None, description="Filter by specific streamer username")
):
    """Debug endpoint to list contents of recordings directory"""
    
    result = {
        "base_recordings_dir": "/recordings",
        "filter": {
            "streamer_username": streamer_username
        },
        "directories": []
    }
    
    try:
        base_dir = Path("/recordings")
        if base_dir.exists():
            result["base_recordings_dir_exists"] = True
            
            if streamer_username:
                # Validate streamer_username using strict whitelist approach
                if not re.match(r'^[a-zA-Z0-9\-_. ]+$', streamer_username):
                    result["error"] = "Invalid streamer username format"
                else:
                    # Get list of valid streamer directories from filesystem (whitelist approach)
                    valid_streamers = []
                    if base_dir.exists():
                        for item in base_dir.iterdir():
                            if item.is_dir():
                                valid_streamers.append(item.name)
                    
                    # Check if requested streamer exists in whitelist
                    if streamer_username not in valid_streamers:
                        result["error"] = f"Streamer directory not found: {streamer_username}"
                        result["available_streamers"] = valid_streamers
                    else:
                        # Safe path construction using validated name from filesystem
                        streamer_dir = base_dir / streamer_username
                        streamer_info = {
                            "name": streamer_dir.name,
                            "path": str(streamer_dir),
                            "subdirectories": [],
                            "total_files": 0,
                            "total_size_mb": 0
                        }
                        
                        # List season directories
                        for season_dir in streamer_dir.iterdir():
                            if season_dir.is_dir():
                                season_info = {
                                    "name": season_dir.name,
                                    "path": str(season_dir),
                                    "files": [],
                                    "file_count": 0,
                                    "total_size_mb": 0
                                }
                                
                                # List files in season directory
                                for file in season_dir.iterdir():
                                    if file.is_file():
                                        file_size = file.stat().st_size
                                        season_info["files"].append({
                                            "name": file.name,
                                            "size": file_size,
                                            "size_mb": round(file_size / (1024*1024), 2),
                                            "path": str(file),
                                            "extension": file.suffix
                                        })
                                        season_info["file_count"] += 1
                                        season_info["total_size_mb"] += round(file_size / (1024*1024), 2)
                                
                                streamer_info["subdirectories"].append(season_info)
                                streamer_info["total_files"] += season_info["file_count"]
                                streamer_info["total_size_mb"] += season_info["total_size_mb"]
                        
                        result["directories"].append(streamer_info)
            
            else:
                # List all streamer directories (with performance limits)
                for streamer_dir in base_dir.iterdir():
                    if streamer_dir.is_dir():
                        streamer_info = {
                            "name": streamer_dir.name,
                            "path": str(streamer_dir),
                            "subdirectories": [],
                            "total_files": 0,
                            "total_size_mb": 0
                        }
                        
                        # List season directories (limit to avoid performance issues)
                        season_count = 0
                        for season_dir in streamer_dir.iterdir():
                            if season_dir.is_dir() and season_count < 10:  # Limit seasons shown
                                season_info = {
                                    "name": season_dir.name,
                                    "path": str(season_dir),
                                    "files": [],
                                    "file_count": 0,
                                    "total_size_mb": 0
                                }
                                
                                # Count files without listing all (for performance)
                                file_count = 0
                                total_size = 0
                                for file in season_dir.iterdir():
                                    if file.is_file():
                                        file_count += 1
                                        total_size += file.stat().st_size
                                        
                                        # Only list first 5 files for preview
                                        if len(season_info["files"]) < 5:
                                            season_info["files"].append({
                                                "name": file.name,
                                                "size": file.stat().st_size,
                                                "size_mb": round(file.stat().st_size / (1024*1024), 2),
                                                "path": str(file),
                                                "extension": file.suffix
                                            })
                                
                                season_info["file_count"] = file_count
                                season_info["total_size_mb"] = round(total_size / (1024*1024), 2)
                                
                                streamer_info["subdirectories"].append(season_info)
                                streamer_info["total_files"] += file_count
                                streamer_info["total_size_mb"] += season_info["total_size_mb"]
                                season_count += 1
                        
                        result["directories"].append(streamer_info)
        else:
            result["base_recordings_dir_exists"] = False
            
    except Exception as e:
        result["error"] = "An internal error occurred while accessing recordings directory"
    
    return result




