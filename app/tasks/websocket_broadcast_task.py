"""
Background task for broadcasting periodic WebSocket updates
"""

import asyncio
import logging
from typing import Dict, List, Any
from app.dependencies import websocket_manager
from app.database import SessionLocal
from app.models import Recording
from sqlalchemy import and_
from datetime import datetime

logger = logging.getLogger("streamvault")

class WebSocketBroadcastTask:
    """Handles periodic WebSocket broadcasts for real-time updates"""
    
    def __init__(self):
        self.is_running = False
        self._task = None
    
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
        """Main broadcast loop that runs every 10 seconds"""
        try:
            while self.is_running:
                try:
                    # Broadcast active recordings
                    await self._broadcast_active_recordings()
                    
                    # Wait 10 seconds before next broadcast
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.error(f"Error in WebSocket broadcast loop: {e}")
                    await asyncio.sleep(5)  # Shorter wait on error
                    
        except asyncio.CancelledError:
            logger.info("WebSocket broadcast loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in WebSocket broadcast loop: {e}")
    
    async def _broadcast_active_recordings(self):
        """Broadcast current active recordings to all WebSocket clients"""
        try:
            with SessionLocal() as db:
                # Get all currently active recordings
                active_recordings = db.query(Recording).filter(
                    and_(
                        Recording.status == "recording",
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
                
                # Send via WebSocket if we have connected clients
                if websocket_manager and len(websocket_manager.active_connections) > 0:
                    await websocket_manager.send_active_recordings_update(recordings_data)
                    logger.debug(f"Broadcasted {len(recordings_data)} active recordings to {len(websocket_manager.active_connections)} clients")
                
        except Exception as e:
            logger.error(f"Error broadcasting active recordings: {e}")
    
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
