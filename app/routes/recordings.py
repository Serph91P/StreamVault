"""
Recordings API Routes

Provides endpoints for recordings management and querying.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
import logging

from app.database import get_db
from app.models import Recording, Streamer
from app.dependencies import get_current_user

router = APIRouter(prefix="/recordings", tags=["recordings"])
logger = logging.getLogger("streamvault")

@router.get("/latest")
async def get_latest_recording(db: Session = Depends(get_db)):
    """Get the most recent completed recording for performance optimization"""
    try:
        latest_recording = db.query(Recording)\
            .filter(Recording.status == 'completed')\
            .order_by(desc(Recording.ended_at))\
            .first()
        
        if not latest_recording:
            return {"recording": None}
        
        # Get streamer info
        streamer = db.query(Streamer).filter(Streamer.id == latest_recording.streamer_id).first()
        
        result = {
            "id": latest_recording.id,
            "streamer_id": latest_recording.streamer_id,
            "streamer_name": streamer.username if streamer else "Unknown",
            "title": latest_recording.title,
            "started_at": latest_recording.started_at.isoformat() if latest_recording.started_at else None,
            "ended_at": latest_recording.ended_at.isoformat() if latest_recording.ended_at else None,
            "duration": latest_recording.duration,
            "file_path": latest_recording.file_path,
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
        recent_recordings = db.query(Recording)\
            .filter(Recording.status == 'completed')\
            .order_by(desc(Recording.ended_at))\
            .limit(limit)\
            .all()
        
        # Get streamer info for all recordings
        streamer_ids = [r.streamer_id for r in recent_recordings]
        streamers = db.query(Streamer).filter(Streamer.id.in_(streamer_ids)).all()
        streamer_map = {s.id: s.username for s in streamers}
        
        results = []
        for recording in recent_recordings:
            result = {
                "id": recording.id,
                "streamer_id": recording.streamer_id,
                "streamer_name": streamer_map.get(recording.streamer_id, "Unknown"),
                "title": recording.title,
                "started_at": recording.started_at.isoformat() if recording.started_at else None,
                "ended_at": recording.ended_at.isoformat() if recording.ended_at else None,
                "duration": recording.duration,
                "file_path": recording.file_path,
                "status": recording.status
            }
            results.append(result)
        
        return {"recordings": results}
    except Exception as e:
        logger.error(f"Error getting recent recordings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent recordings")
