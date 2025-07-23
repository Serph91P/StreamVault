"""
Temporary Debug Script to diagnose video-related issues
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Stream, Streamer, Recording
from app.utils.streamer_cache import get_valid_streamers, get_cache_info, invalidate_streamer_cache
from pathlib import Path
import os
import re
from typing import Optional

router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.get("/videos-database")
async def debug_videos_database(
    db: Session = Depends(get_db),
    streamer_username: Optional[str] = Query(None, description="Filter by specific streamer username")
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

@router.get("/recordings-directory")
async def debug_recordings_directory(
    streamer_username: Optional[str] = Query(None, description="Filter by specific streamer username")
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
                # List all streamer directories
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


@router.get("/streamer-cache")
async def debug_streamer_cache():
    """Debug endpoint to view and manage streamer directory cache"""
    cache_info = get_cache_info()
    
    return {
        "cache_status": cache_info,
        "operations": {
            "refresh": "POST /api/debug/streamer-cache/refresh",
            "invalidate": "POST /api/debug/streamer-cache/invalidate"
        }
    }


@router.post("/streamer-cache/refresh")
async def refresh_streamer_cache():
    """Force refresh of streamer directory cache"""
    base_recordings_dir = Path("/recordings")
    valid_streamers = get_valid_streamers(base_recordings_dir, force_refresh=True)
    
    return {
        "message": "Streamer cache refreshed",
        "streamer_count": len(valid_streamers),
        "streamers": valid_streamers
    }


@router.post("/streamer-cache/invalidate")
async def invalidate_cache():
    """Invalidate streamer directory cache"""
    invalidate_streamer_cache()
    
    return {
        "message": "Streamer cache invalidated"
    }
