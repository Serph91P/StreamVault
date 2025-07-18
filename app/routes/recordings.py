"""
Recordings API Routes

Provides endpoints for recordings management and querying.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_
from typing import List, Optional
import logging

from app.database import get_db
from app.models import Recording, Streamer, Stream
from app.dependencies import get_current_user

router = APIRouter(prefix="/recordings", tags=["recordings"])
logger = logging.getLogger("streamvault")

@router.get("/latest")
async def get_latest_recording(db: Session = Depends(get_db)):
    """Get the most recent completed recording for performance optimization"""
    try:
        latest_recording = db.query(Recording).options(
            joinedload(Recording.stream).joinedload(Stream.streamer)
        ).filter(Recording.status == 'completed')\
            .order_by(desc(Recording.end_time))\
            .first()
        
        if not latest_recording:
            return {"recording": None}
        
        # Get streamer info
        streamer = None
        if latest_recording.stream:
            streamer = latest_recording.stream.streamer
        
        result = {
            "id": latest_recording.id,
            "stream_id": latest_recording.stream_id,
            "streamer_name": streamer.username if streamer else "Unknown",
            "title": latest_recording.stream.title if latest_recording.stream else "No Title",
            "started_at": latest_recording.start_time.isoformat() if latest_recording.start_time else None,
            "ended_at": latest_recording.end_time.isoformat() if latest_recording.end_time else None,
            "duration": latest_recording.duration,
            "file_path": latest_recording.path,
            "status": latest_recording.status
        }
        
        return {"recording": result}
    except Exception as e:
        logger.error(f"Error getting latest recording: {e}")
        raise HTTPException(status_code=500, detail="Failed to get latest recording")

@router.get("/recent")
async def get_recent_recordings(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recent recordings for performance optimization"""
    try:
        recent_recordings = db.query(Recording).options(
            joinedload(Recording.stream).joinedload(Stream.streamer)
        ).filter(Recording.status == 'completed')\
            .order_by(desc(Recording.end_time))\
            .limit(limit)\
            .all()
        
        # Get streamer info for all recordings
        results = []
        for recording in recent_recordings:
            streamer = None
            if recording.stream:
                streamer = recording.stream.streamer
                
            result = {
                "id": recording.id,
                "stream_id": recording.stream_id,
                "streamer_name": streamer.username if streamer else "Unknown",
                "title": recording.stream.title if recording.stream else "No Title",
                "started_at": recording.start_time.isoformat() if recording.start_time else None,
                "ended_at": recording.end_time.isoformat() if recording.end_time else None,
                "duration": recording.duration,
                "file_path": recording.path,
                "status": recording.status
            }
            results.append(result)
        
        return {"recordings": results}
    except Exception as e:
        logger.error(f"Error getting recent recordings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent recordings")
