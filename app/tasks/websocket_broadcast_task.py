"""
Background task for broadcasting periodic WebSocket updates
"""

import asyncio
import logging
import hashlib
import json
from typing import Dict, List, Any
from app.dependencies import websocket_manager
from app.database import SessionLocal
from app.models import Recording, Stream
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from datetime import datetime

logger = logging.getLogger("streamvault")

class WebSocketBroadcastTask:
    """Handles periodic WebSocket broadcasts for real-time updates"""
    
    def __init__(self):
        self.is_running = False
        self._task = None
        # Cache for detecting changes
        self._last_recordings_hash = None
        self._last_queue_hash = None
    
    async def start(self):
        """Start the background broadcast task"""
        if self.is_running:
            logger.warning("WebSocket broadcast task already running")
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        logger.info("WebSocket broadcast task started")
    
    async def stop(self):
        """Stop the background broadcast task"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("WebSocket broadcast task stopped")
    
    async def _broadcast_loop(self):
        """Main broadcast loop that runs with optimized frequency"""
        try:
            recording_update_counter = 0
            queue_update_counter = 0
            
            while self.is_running:
                try:
                    # Broadcast active recordings every 30 seconds (reduced from 10)
                    if recording_update_counter % 3 == 0:
                        await self._broadcast_active_recordings()
                    
                    # Broadcast background queue status every 60 seconds (reduced from 10)
                    if queue_update_counter % 6 == 0:
                        await self._broadcast_background_queue_status()
                    
                    recording_update_counter += 1
                    queue_update_counter += 1
                    
                    # Wait 10 seconds before next cycle (only counters change)
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.error(f"Error in WebSocket broadcast loop: {e}")
                    await asyncio.sleep(5)  # Shorter wait on error
                    
        except asyncio.CancelledError:
            logger.info("WebSocket broadcast loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in WebSocket broadcast loop: {e}")
    
    async def _broadcast_active_recordings(self):
        """Broadcast current active recordings to all WebSocket clients (only on changes)"""
        try:
            with SessionLocal() as db:
                # Get all currently active recordings with joined relationships
                active_recordings = db.query(Recording).options(
                    joinedload(Recording.stream).joinedload(Stream.streamer)
                ).filter(
                    and_(
                        Recording.status.in_(["recording", "processing"]),
                        Recording.path.isnot(None)
                    )
                ).all()
                
                # Convert to dict format for frontend
                recordings_data = []
                for recording in active_recordings:
                    recordings_data.append({
                        "id": recording.id,
                        "stream_id": recording.stream_id,
                        "streamer_id": recording.stream.streamer_id if recording.stream else None,
                        "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                        "title": recording.stream.title if recording.stream else "No Title", 
                        "started_at": recording.start_time.isoformat() if recording.start_time else None,
                        "file_path": recording.path,
                        "status": recording.status,
                        "duration": self._calculate_duration(recording.start_time) if recording.start_time else 0
                    })
                
                # Calculate hash of current data to check for changes
                current_hash = hashlib.md5(json.dumps(recordings_data, sort_keys=True).encode()).hexdigest()
                
                # Only send if data has changed or no previous hash exists
                if current_hash != self._last_recordings_hash:
                    self._last_recordings_hash = current_hash
                    
                    # Send via WebSocket if we have connected clients
                    if websocket_manager and len(websocket_manager.active_connections) > 0:
                        await websocket_manager.send_active_recordings_update(recordings_data)
                        logger.debug(f"Broadcasted {len(recordings_data)} active recordings to {len(websocket_manager.active_connections)} clients (data changed)")
                    elif websocket_manager:
                        logger.debug(f"No WebSocket clients connected - skipping broadcast of {len(recordings_data)} recordings")
                    else:
                        logger.warning("WebSocket manager not available - cannot broadcast recordings")
                else:
                    logger.debug(f"Active recordings data unchanged - skipping broadcast ({len(recordings_data)} recordings)")
                
        except Exception as e:
            logger.error(f"Error broadcasting active recordings: {e}")
    
    async def _broadcast_background_queue_status(self):
        """Broadcast current background queue status to all WebSocket clients"""
        try:
            from app.services.background_queue_service import background_queue_service
            
            if background_queue_service:
                # Get queue statistics safely
                try:
                    queue_stats = background_queue_service.get_queue_statistics()
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
                    
                    # Prepare data for frontend
                    queue_data = {
                        "stats": queue_stats,
                        "active_tasks": active_tasks_data,
                        "recent_tasks": recent_tasks_data
                    }
                    
                    # Calculate hash of current data to check for changes
                    current_hash = hashlib.md5(json.dumps(queue_data, sort_keys=True).encode()).hexdigest()
                    
                    # Only send if data has changed or no previous hash exists
                    if current_hash != self._last_queue_hash:
                        self._last_queue_hash = current_hash
                        
                        # Send via WebSocket if we have connected clients
                        if websocket_manager and len(websocket_manager.active_connections) > 0:
                            message = {
                                "type": "background_queue_update",
                                "data": queue_data
                            }
                            await websocket_manager.send_notification(message)
                            logger.debug(f"Broadcasted queue status to {len(websocket_manager.active_connections)} clients: {len(active_tasks_data)} active, {len(recent_tasks_data)} recent (data changed)")
                    else:
                        logger.debug(f"Queue data unchanged - skipping broadcast ({len(active_tasks_data)} active tasks)")
                    
                except AttributeError as e:
                    logger.warning(f"Background queue service method not available: {e}")
                except Exception as e:
                    logger.error(f"Error getting queue data: {e}")
                
        except ImportError as e:
            logger.warning(f"Background queue service not available: {e}")
        except Exception as e:
            logger.error(f"Error broadcasting background queue status: {e}")
    
    def _calculate_duration(self, start_time: datetime) -> int:
        """Calculate recording duration in seconds"""
        if not start_time:
            return 0
        
        if start_time.tzinfo is not None:
            # Both are timezone-aware, use UTC for calculation
            from datetime import timezone
            now = datetime.now(timezone.utc)
            # Convert start_time to UTC if it's not already
            if start_time.tzinfo != timezone.utc:
                start_time = start_time.astimezone(timezone.utc)
        else:
            # Both are naive, assume UTC
            now = datetime.utcnow()
        
        delta = now - start_time
        return int(delta.total_seconds())

# Global instance
websocket_broadcast_task = WebSocketBroadcastTask()
