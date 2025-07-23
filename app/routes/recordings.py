"""
Recordings API Routes

Provides endpoints for recordings management and querying.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_
from typing import List, Optional
import logging

from app.database import get_db, SessionLocal
from app.models import Recording, Streamer, Stream
from app.dependencies import get_current_user
from app.services.recording.recording_service import RecordingService
from app.services.system.logging_service import logging_service
from app.services.communication.websocket_manager import websocket_manager

router = APIRouter(prefix="/recordings", tags=["recordings"])
logger = logging.getLogger("streamvault")

recording_service = None

def get_recording_service():
    """Lazy initialization of recording service"""
    global recording_service
    if recording_service is None:
        recording_service = RecordingService()
    return recording_service

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

@router.post("/force-stop")
async def force_stop_recording(request_data: dict):
    """Force stop a recording for a specific streamer"""
    try:
        streamer_id = request_data.get("streamer_id")
        if not streamer_id:
            raise HTTPException(status_code=400, detail="streamer_id is required")
        
        # Get streamer info for notifications
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            streamer_name = streamer.username if streamer else f"Streamer {streamer_id}"
        
        # Log the force stop request
        logging_service.log_recording_activity("FORCE_STOP_REQUEST", f"Streamer {streamer_id}", "Force stop requested via API")
        
        result = await get_recording_service().stop_recording_manual(streamer_id)
        if result:
            logging_service.log_recording_activity("FORCE_STOP_SUCCESS", f"Streamer {streamer_id}", "Recording force stopped successfully via API")
            
            # Send success toast notification
            await websocket_manager.send_toast_notification(
                toast_type="success",
                title=f"Recording Stopped - {streamer_name}",
                message="Recording force stopped successfully!"
            )
            
            return {"status": "success", "message": "Recording force stopped successfully"}
        else:
            logging_service.log_recording_activity("FORCE_STOP_FAILED", f"Streamer {streamer_id}", "No active recording found", "warning")
            
            # Send warning toast notification
            await websocket_manager.send_toast_notification(
                toast_type="warning",
                title=f"Force Stop Recording - {streamer_name}",
                message="No active recording found to stop."
            )
            
            return {"status": "error", "message": "No active recording found"}
    except Exception as e:
        logging_service.log_recording_error(streamer_id, f"Streamer {streamer_id}", "API_FORCE_STOP_ERROR", str(e))
        logger.error(f"Error force stopping recording: {e}")
        
        # Send error toast notification
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                streamer_name = streamer.username if streamer else f"Streamer {streamer_id}"
                
            await websocket_manager.send_toast_notification(
                toast_type="error",
                title=f"Force Stop Recording - {streamer_name}",
                message=f"Failed to force stop recording: {str(e)}"
            )
        except Exception as notification_error:
            logger.error(f"Failed to send error notification: {notification_error}")
        
        raise HTTPException(status_code=500, detail=str(e))
