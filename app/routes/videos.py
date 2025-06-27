from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, FileResponse
import os
import urllib.parse
from typing import List
import logging
from pathlib import Path
import mimetypes
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.models import RecordingSettings, Stream, Streamer
from app.utils.security_enhanced import safe_file_access, safe_error_message, list_safe_directory

logger = logging.getLogger("streamvault")
router = APIRouter(
    prefix="/api",
    tags=["videos"]
)

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
async def get_videos(request: Request, db: Session = Depends(get_db)):
    """Get all videos from database with file verification"""
    # Check authentication via session cookie
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate session
    from app.services.auth_service import AuthService
    auth_service = AuthService(db)
    if not await auth_service.validate_session(session_token):
        raise HTTPException(status_code=401, detail="Invalid session")
    
    videos = []
    
    try:
        # Query all streams that have recording paths
        streams = db.query(Stream, Streamer).join(
            Streamer, Stream.streamer_id == Streamer.id
        ).filter(
            Stream.recording_path.isnot(None),
            Stream.recording_path != ""
        ).order_by(Stream.started_at.desc()).all()
        
        logger.debug(f"Found {len(streams)} streams with recording paths in database")
        
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
                        "thumbnail_url": None  # TODO: Generate thumbnails
                    }
                    videos.append(video_info)
                    logger.debug(f"Added video: {stream.title} by {streamer.username}")
                else:
                    logger.warning(f"Recording file not found: {stream.recording_path}")
                    
            except Exception as e:
                logger.error(f"Error processing stream {stream.id}: {e}")
                continue
        
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
        from app.services.auth_service import AuthService
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
        return {"error": str(e), "type": type(e).__name__}

@router.get("/videos/stream/{stream_id}")
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
            from app.services.auth_service import AuthService
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
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid range header")
        else:
            # No range request, stream entire file
            def generate_file():
                with open(file_path, 'rb') as f:
                    while True:
                        data = f.read(8192)
                        if not data:
                            break
                        yield data
            
            headers = {
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Type": mime_type
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

@router.get("/videos/{streamer_name}/{filename}")
async def stream_video(streamer_name: str, filename: str, request: Request, db: Session = Depends(get_db)):
    """Stream a video file with range request support - CodeQL-safe implementation"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        from app.services.auth_service import AuthService
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
async def get_streamer_videos(streamer_name: str, request: Request, db: Session = Depends(get_db)):
    """Get all videos for a specific streamer - CodeQL-safe implementation"""
    try:
        # Check authentication via session cookie
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate session
        from app.services.auth_service import AuthService
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
        from app.services.auth_service import AuthService
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
        return {"error": "An internal error has occurred."}

@router.get("/videos/streamer/{streamer_id}")
async def get_videos_by_streamer(streamer_id: int, request: Request, db: Session = Depends(get_db)):
    """Get all videos for a specific streamer"""
    # Check authentication via session cookie
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate session
    from app.services.auth_service import AuthService
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
                        "thumbnail_url": None
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
        from app.services.auth_service import AuthService
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
        
        # Search for the file in the recordings directory
        recordings_path = Path(recordings_dir)
        if not recordings_path.exists():
            raise HTTPException(status_code=404, detail="Recordings directory not found")
        
        # Construct the full file path
        potential_path = recordings_path / sanitized_filename
        try:
            normalized_path = potential_path.resolve(strict=True)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Validate that the path is within the recordings directory and not a symbolic link outside it
        if os.path.commonpath([recordings_path.resolve(), normalized_path]) != str(recordings_path.resolve()) or not normalized_path.is_file():
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Check if the file is a valid video file
        if not is_video_file(str(normalized_path)):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        file_path = normalized_path
        
        # Get file info
        try:
            file_size = file_path.stat().st_size
        except OSError:
            raise HTTPException(status_code=500, detail="Error accessing file")
        
        # Get MIME type
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
                    with open(file_path, 'rb') as f:
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
        
        # Return full file
        return FileResponse(
            file_path,
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
            from app.services.auth_service import AuthService
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
