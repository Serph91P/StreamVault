"""
Temporäres Debug-Script um Videos-Problem zu diagnostizieren
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Stream, Streamer, Recording
from pathlib import Path
import os

router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.get("/videos-database")
async def debug_videos_database(db: Session = Depends(get_db)):
    """Debug endpoint to see what's in the database vs filesystem"""
    
    result = {
        "streams": [],
        "recordings": [],
        "filesystem_check": {},
        "summary": {}
    }
    
    # Check streams table
    streams = db.query(Stream, Streamer).join(
        Streamer, Stream.streamer_id == Streamer.id
    ).filter(
        Streamer.username == "herrmaximal"
    ).order_by(Stream.started_at.desc()).all()
    
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
    
    # Check recordings table
    recordings = db.query(Recording, Stream, Streamer).join(
        Stream, Recording.stream_id == Stream.id
    ).join(
        Streamer, Stream.streamer_id == Streamer.id
    ).filter(
        Streamer.username == "herrmaximal"
    ).order_by(Recording.start_time.desc()).all()
    
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
    
    # Check filesystem directly
    recordings_dir = Path("/recordings/herrmaximal")
    if recordings_dir.exists():
        result["filesystem_check"]["recordings_dir_exists"] = True
        
        # List all subdirectories
        subdirs = []
        for item in recordings_dir.iterdir():
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
async def debug_recordings_directory():
    """Debug endpoint to list contents of recordings directory"""
    
    result = {
        "base_recordings_dir": "/recordings",
        "herrmaximal_dir": "/recordings/herrmaximal",
        "directories": []
    }
    
    try:
        base_dir = Path("/recordings")
        if base_dir.exists():
            result["base_recordings_dir_exists"] = True
            
            # List all streamer directories
            for streamer_dir in base_dir.iterdir():
                if streamer_dir.is_dir():
                    streamer_info = {
                        "name": streamer_dir.name,
                        "path": str(streamer_dir),
                        "subdirectories": []
                    }
                    
                    # List season directories
                    for season_dir in streamer_dir.iterdir():
                        if season_dir.is_dir():
                            season_info = {
                                "name": season_dir.name,
                                "path": str(season_dir),
                                "files": []
                            }
                            
                            # List files in season directory
                            for file in season_dir.iterdir():
                                if file.is_file():
                                    season_info["files"].append({
                                        "name": file.name,
                                        "size": file.stat().st_size,
                                        "path": str(file),
                                        "extension": file.suffix
                                    })
                            
                            streamer_info["subdirectories"].append(season_info)
                    
                    result["directories"].append(streamer_info)
        else:
            result["base_recordings_dir_exists"] = False
            
    except Exception as e:
        result["error"] = str(e)
    
    return result
