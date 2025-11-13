"""
Status API Routes

Provides real-time status endpoints that work independently of WebSocket connections.
This ensures the frontend can always get current state, regardless of WebSocket connectivity.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone

from app.database import get_db, SessionLocal
from app.models import Recording, Stream, Streamer, NotificationSettings, PushSubscription, GlobalSettings, StreamEvent
from app.schemas import ActiveRecordingSchema
from app.services.background_queue_service import background_queue_service
from app.services.unified_image_service import unified_image_service
from sqlalchemy import text

router = APIRouter(prefix="/status", tags=["status"])
logger = logging.getLogger("streamvault")

@router.get("/recordings-active")
async def check_recordings_active() -> Dict[str, Any]:
    """
    Check if any recordings are currently active.
    
    This endpoint is designed for CI/CD and update systems to determine
    if it's safe to perform maintenance/updates.
    
    Returns:
        {
            "has_active_recordings": bool,
            "active_count": int,
            "safe_to_update": bool,
            "active_streamers": List[str],  # List of streamer names with active recordings
            "timestamp": str
        }
    """
    try:
        with SessionLocal() as db:
            # Get active recordings with streamer info
            active_recordings = db.query(Recording).join(Stream).join(Streamer).filter(
                Recording.status == "recording"
            ).options(
                joinedload(Recording.stream).joinedload(Stream.streamer)
            ).all()
            
            active_count = len(active_recordings)
            active_streamers = []
            
            for recording in active_recordings:
                try:
                    if recording.stream and recording.stream.streamer:
                        active_streamers.append(recording.stream.streamer.username)
                except Exception as e:
                    logger.warning(f"Error processing recording {recording.id}: {e}")
            
            return {
                "has_active_recordings": active_count > 0,
                "active_count": active_count,
                "safe_to_update": active_count == 0,  # Safe when no recordings active
                "active_streamers": active_streamers,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "No active recordings - safe to update" if active_count == 0 else f"{active_count} recording(s) in progress - wait before updating"
            }
            
    except Exception as e:
        logger.error(f"Error checking active recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check active recordings status")

@router.get("/system")
async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    try:
        with SessionLocal() as db:
            # Get active recordings count
            active_recordings_count = db.query(Recording).filter(
                Recording.status == "recording"
            ).count()
            
            # Get total streamers count
            total_streamers = db.query(Streamer).count()
            
            # Get live streamers (those with recent active streams)
            live_streamers_count = db.query(Streamer).join(Stream).filter(
                and_(
                    Stream.ended_at.is_(None),
                    Stream.started_at.isnot(None)
                )
            ).distinct().count()
            
            # Get queue status
            queue_stats = {}
            if background_queue_service:
                try:
                    queue_stats = background_queue_service.get_queue_statistics()
                except Exception as e:
                    logger.warning(f"Could not get queue statistics: {e}")
                    queue_stats = {"error": "Queue service unavailable"}
            
            return {
                "system": {
                    "active_recordings": active_recordings_count,
                    "total_streamers": total_streamers,
                    "live_streamers": live_streamers_count,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "background_queue": queue_stats
            }
            
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")

@router.get("/active-recordings")
async def get_active_recordings_status() -> Dict[str, Any]:
    """Get current active recordings status (REST endpoint)"""
    try:
        with SessionLocal() as db:
            # Get active recordings with full details
            active_recordings = db.query(Recording).join(Stream).join(Streamer).filter(
                Recording.status == "recording"
            ).options(
                joinedload(Recording.stream).joinedload(Stream.streamer)
            ).all()
            
            recordings_data = []
            for recording in active_recordings:
                try:
                    stream = recording.stream
                    if stream and stream.streamer:
                        # Calculate duration
                        duration = 0
                        if recording.start_time:
                            duration = int((datetime.now(timezone.utc) - recording.start_time).total_seconds())
                        
                        recordings_data.append({
                            "id": recording.id,
                            "stream_id": recording.stream_id,
                            "streamer_id": stream.streamer_id,
                            "streamer_name": stream.streamer.username,
                            "title": stream.title or '',
                            "started_at": recording.start_time.isoformat() if recording.start_time else '',
                            "file_path": recording.path or '',
                            "status": recording.status,
                            "duration": duration
                        })
                except Exception as e:
                    logger.warning(f"Error processing recording {recording.id}: {e}")
                    continue
            
            return {
                "active_recordings": recordings_data,
                "count": len(recordings_data),
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting active recordings status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active recordings status")

@router.get("/background-queue")
async def get_background_queue_status() -> Dict[str, Any]:
    """Get current background queue status"""
    try:
        if not background_queue_service:
            return {
                "error": "Background queue service not available",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Get queue statistics
        stats = background_queue_service.get_queue_statistics()
        active_tasks = background_queue_service.get_active_tasks()
        recent_tasks = background_queue_service.get_completed_tasks()
        
        # Convert tasks to serializable format
        active_tasks_data = []
        for task_id, task in active_tasks.items():
            active_tasks_data.append({
                "id": task_id,
                "task_type": task.task_type,
                "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "streamer_name": task.payload.get("streamer_name", "Unknown"),
                "stream_id": task.payload.get("stream_id"),
                "recording_id": task.payload.get("recording_id")
            })
        
        recent_tasks_data = []
        for task_id, task in list(recent_tasks.items())[-10:]:  # Last 10 tasks
            recent_tasks_data.append({
                "id": task_id,
                "task_type": task.task_type,
                "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "streamer_name": task.payload.get("streamer_name", "Unknown"),
                "error_message": task.error_message
            })
        
        return {
            "stats": stats,
            "active_tasks": active_tasks_data,
            "recent_tasks": recent_tasks_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting background queue status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get background queue status")

@router.get("/health")
async def get_health_status() -> Dict[str, Any]:
    """Get basic health status for monitoring"""
    try:
        # Basic database connectivity test
        with SessionLocal() as db:
            db.execute("SELECT 1")
        
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check background queue service
    queue_status = "healthy" if background_queue_service else "unavailable"
    
    overall_status = "healthy" if db_status == "healthy" else "degraded"
    
    return {
        "status": overall_status,
        "components": {
            "database": db_status,
            "background_queue": queue_status
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/streamers")
async def get_streamers_status() -> Dict[str, Any]:
    """Get current streamers status (online/offline/recording states)"""
    try:
        with SessionLocal() as db:
            # Get streamers with their current status
            streamers = db.query(Streamer).all()
            
            streamer_status = []
            online_count = 0
            recording_count = 0
            
            for streamer in streamers:
                # Check if currently recording
                active_recording = db.query(Recording).filter(
                    and_(
                        Recording.stream_id.in_(
                            db.query(Stream.id).filter(Stream.streamer_id == streamer.id)
                        ),
                        Recording.status == "recording"
                    )
                ).first()
                
                is_recording = active_recording is not None
                if is_recording:
                    recording_count += 1
                
                # Check if streamer is live (has active stream)
                latest_stream = db.query(Stream).filter(
                    Stream.streamer_id == streamer.id
                ).order_by(Stream.created_at.desc()).first()
                
                is_live = latest_stream and latest_stream.ended_at is None if latest_stream else False
                if is_live:
                    online_count += 1
                
                # Get profile image URL safely
                profile_image_url = None
                if unified_image_service:
                    try:
                        profile_image_url = unified_image_service.get_profile_image_url(
                            streamer.id, 
                            streamer.profile_image_url
                        )
                    except Exception as e:
                        logger.warning(f"Failed to get profile image URL for streamer {streamer.id}: {e}")
                
                # Get last known info from most recent stream (for offline streamers)
                last_title = None
                last_category = None
                language = None
                
                if latest_stream:
                    last_title = latest_stream.title
                    last_category = latest_stream.category_name
                    language = latest_stream.language
                
                streamer_status.append({
                    "id": streamer.id,
                    "name": streamer.username,
                    "display_name": streamer.display_name,
                    "twitch_id": streamer.twitch_id,
                    "profile_image_url": profile_image_url,
                    "is_live": is_live,
                    "is_recording": is_recording,
                    "is_favorite": streamer.is_favorite,
                    "auto_record": streamer.auto_record,
                    "last_seen": latest_stream.created_at.isoformat() if latest_stream else None,
                    "current_title": latest_stream.title if latest_stream and is_live else None,
                    "current_category": latest_stream.category_name if latest_stream and is_live else None,
                    "last_title": last_title,
                    "last_category": last_category,
                    "language": language
                })
            
            return {
                "streamers": streamer_status,
                "summary": {
                    "total": len(streamers),
                    "online": online_count,
                    "recording": recording_count,
                    "offline": len(streamers) - online_count
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get streamers status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get streamers status: {str(e)}")

@router.get("/streams")
async def get_streams_status() -> Dict[str, Any]:
    """Get current streams status and recent activity"""
    try:
        with SessionLocal() as db:
            # Get recent streams (last 24 hours)
            from datetime import timedelta, timezone
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            
            recent_streams = db.query(Stream).filter(
                Stream.created_at >= recent_cutoff
            ).order_by(Stream.created_at.desc()).limit(50).all()
            
            # Get live streams
            live_streams = db.query(Stream).filter(Stream.ended_at.is_(None)).all()
            
            streams_data = []
            for stream in recent_streams:
                # Check if has recording
                recording = db.query(Recording).filter(
                    Recording.stream_id == stream.id
                ).first()
                
                is_live = stream.ended_at is None
                duration = None
                if is_live and stream.started_at:
                    # Ensure both datetimes are timezone-aware
                    now_utc = datetime.now(timezone.utc)
                    start_time = stream.started_at
                    
                    # If started_at is naive, assume UTC
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    
                    duration = (now_utc - start_time).total_seconds()
                
                streams_data.append({
                    "id": stream.id,
                    "streamer_name": stream.streamer.username if stream.streamer else "Unknown",
                    "title": stream.title,
                    "category": stream.category_name,
                    "is_live": is_live,
                    "has_recording": recording is not None,
                    "recording_status": recording.status if recording else None,
                    "started_at": stream.started_at.isoformat() if stream.started_at else None,
                    "duration": duration
                })
            
            return {
                "streams": streams_data,
                "summary": {
                    "recent_count": len(recent_streams),
                    "live_count": len(live_streams),
                    "recorded_count": len([s for s in streams_data if s["has_recording"]])
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get streams status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get streams status: {str(e)}")

@router.get("/notifications")
async def get_notifications_status() -> Dict[str, Any]:
    """Get notification system status and recent notifications"""
    try:
        with SessionLocal() as db:
            # Get notification settings
            notification_settings = db.query(NotificationSettings).all()
            
            # Get push subscriptions
            push_subscriptions = db.query(PushSubscription).filter(
                PushSubscription.is_active == True
            ).count()
            
            # Get global settings
            global_settings = db.query(GlobalSettings).first()
            
            # Get recent events (last 24 hours) if table exists
            recent_events = []
            try:
                from datetime import timedelta
                recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                
                events = db.query(StreamEvent).filter(
                    StreamEvent.timestamp >= recent_cutoff
                ).order_by(StreamEvent.timestamp.desc()).limit(20).all()
                
                for event in events:
                    recent_events.append({
                        "id": event.id,
                        "type": event.event_type,
                        "streamer_name": event.stream.streamer.username if event.stream and event.stream.streamer else "Unknown",
                        "title": event.title,
                        "category_name": event.category_name,
                        "timestamp": event.timestamp.isoformat()
                    })
            except Exception as e:
                logger.warning(f"Could not get recent events: {e}")
            
            return {
                "notification_system": {
                    "enabled": global_settings.notifications_enabled if global_settings else False,
                    "url_configured": bool(global_settings.notification_url) if global_settings else False,
                    "active_subscriptions": push_subscriptions,
                    "streamers_with_notifications": len(notification_settings)
                },
                "recent_events": recent_events,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get notifications status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notifications status: {str(e)}")
